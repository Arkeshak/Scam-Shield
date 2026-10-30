"""Run:  python tests_api_offline.py
Tests the web routes with a fake model (no internet, no API key needed)."""
import io

from fastapi.testclient import TestClient
from PIL import Image

import app.main as m

m.run_agent_fast = m.run_agent = lambda case, ctx, lang="English": {
    "risk": "high", "scam_type": "bank_phishing", "verdict": "Likely scam.", "reasons": ["fake link"],
    "red_flags": ["xyz link"], "next_step": "Ignore it.", "confidence": 0.9, "actions": ["Checked 1 link(s)"],
    "trace": [{"tool": "check_links", "args": '{"links": ["http://xyz"]}', "result": '{"suspicious": true}'}],
}
m.transcribe_file = lambda path, language: "A fictional call asks the listener to pay a fee."
m.call.analyze_call = lambda path, language="English", timings=None: {
    "risk": "high", "scam_type": "fake payment", "verdict": "Do not pay.",
    "reasons": ["Asks for a fee."], "flagged_turns": [{"turn": 1, "trick": "urgency"}],
    "next_step": "Hang up.", "confidence": 0.9,
    "turns": [{"turnId": 1, "speaker": "A", "transcript": "Pay now."}], "transcript": "Pay now.",
    "timings": [{"stage": "Separate speakers", "model": "Muse Voice Transcribe", "ms": 50}], "total_ms": 100,
}
m.llm.analyze_image = lambda data, mime, lang="English": {
    "risk": "high", "scam_type": "x", "verdict": "v", "reasons": [], "red_flags": [],
    "regions": [{"label": "logo", "reason": "wrong logo", "box": [.1, .1, .4, .3]}],
}
m.refine_with_sam = lambda data, mime, regions: [dict(r, source="sam-3.1") for r in regions]

c = TestClient(m.app)
assert c.get("/").status_code == 200
assert c.get("/health").json() == {"ok": True}

# Test /analyze/text has timings, total_ms, and trace
r = c.post("/analyze/text", json={"text": "Verify at http://secure-b4nk-login.xyz now"})
assert r.status_code == 200
data = r.json()
assert data["link_checks"][0]["flags"]
assert "timings" in data and isinstance(data["timings"], list)
assert "total_ms" in data and isinstance(data["total_ms"], int)
assert "trace" in data and isinstance(data["trace"], list)

assert c.post("/analyze/text", json={"text": "  "}).status_code == 400
assert c.post("/analyze/text", json={"text": "A message"}).json()["actions"]

# Test /analyze/image has timings and total_ms
buf = io.BytesIO(); Image.new("RGB", (200, 120), (250, 250, 250)).save(buf, format="PNG")
r = c.post("/analyze/image", files={"file": ("a.png", buf.getvalue(), "image/png")}, data={"language": "English"})
assert r.status_code == 200
img_data = r.json()
assert img_data["regions"][0]["source"] == "sam-3.1"
assert img_data["sources"] == []
assert "timings" in img_data and len(img_data["timings"]) >= 2
assert "total_ms" in img_data

assert c.post("/analyze/image", files={"file": ("bad.png", b"not an image", "image/png")}).status_code == 400
# Truncated PNG header raises SyntaxError in Pillow -- must return 400, not 502
truncated_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8  # PNG magic but no valid IHDR
assert c.post("/analyze/image", files={"file": ("trunc.png", truncated_png, "image/png")}).status_code == 400

# Test /analyze/voice has timings, total_ms, and trace
r = c.post("/analyze/voice", files={"file": ("note.ogg", b"sample audio", "audio/ogg")}, data={"language": "English"})
assert r.status_code == 200
v_data = r.json()
assert v_data["transcript"].startswith("A fictional")
assert "timings" in v_data and "total_ms" in v_data
assert "trace" in v_data

# Test /analyze/call has timings and total_ms
r = c.post("/analyze/call", files={"file": ("call.ogg", b"sample audio", "audio/ogg")}, data={"language": "English"})
assert r.status_code == 200
call_data = r.json()
assert call_data["turns"][0]["speaker"] == "A"
assert "timings" in call_data and "total_ms" in call_data

# Test /api/config and /api/metrics
cfg = c.get("/api/config").json()
assert cfg["models"]["sam"] == "sam-3.1"
assert cfg["models"]["reasoning"]
assert cfg["models"]["segmentation"] == "sam-3.1"

metrics = c.get("/api/metrics").json()
assert metrics["n"] >= 0
assert "development" in metrics or "unseen" in metrics

# Upload size limit test
original_limit = m.MAX_UPLOAD_BYTES
m.MAX_UPLOAD_BYTES = 16
assert c.post("/analyze/image", files={"file": ("large.png", b"x" * 17, "image/png")}).status_code == 413
m.MAX_UPLOAD_BYTES = original_limit

# Sinhala voice error test
original_transcribe = m.transcribe_file
m.transcribe_file = lambda path, language: (_ for _ in ()).throw(ValueError("Voice is not supported in Sinhala yet."))
r = c.post("/analyze/voice", files={"file": ("note.ogg", b"sample audio", "audio/ogg")}, data={"language": "Sinhala"})
assert r.status_code == 400 and "Sinhala" in r.json()["detail"]
m.transcribe_file = original_transcribe

# /api/screenshot_card passes the uploaded screenshot to the card maker
_seen = {}
def _fake_card(scam_type, red_flags, screenshot=None):
    _seen.update(scam_type=scam_type, red_flags=red_flags, screenshot=screenshot)
    return b"fake-png-bytes"
m.make_comparison_card = _fake_card
_buf = io.BytesIO()
Image.new("RGB", (40, 30), "white").save(_buf, format="PNG")
r = c.post("/api/screenshot_card", files={"file": ("a.png", _buf.getvalue(), "image/png")},
           data={"scam_type": "fake bank SMS", "red_flags": '["Asks for OTP", "Urgent"]'})
assert r.status_code == 200 and r.json()["card"].startswith("data:image/png;base64,")
assert _seen["scam_type"] == "fake bank SMS" and _seen["red_flags"] == ["Asks for OTP", "Urgent"]
assert _seen["screenshot"] and _seen["screenshot"][1].startswith("image/")
r = c.post("/api/screenshot_card", files={"file": ("a.png", _buf.getvalue(), "image/png")}, data={"red_flags": "not json"})
assert r.status_code == 200 and _seen["red_flags"] == []
assert c.post("/api/screenshot_card", files={"file": ("bad.png", b"not an image", "image/png")}).status_code == 400

# Chosen language is kept when the agent fails: one more try with the single-call check, then a safe fallback
from app import labels as _labels
_ok = {"risk": "high", "scam_type": "x", "verdict": "HINDI-ANSWER", "reasons": ["r"], "red_flags": [], "next_step": "n", "confidence": 0.9, "actions": []}
_seen = []
def _agent_down(case, ctx, lang="English"):
    raise RuntimeError("timeout")
m.run_agent = _agent_down
m.run_agent_fast = lambda case, ctx, lang="English": _seen.append(lang) or dict(_ok)
r = c.post("/analyze/text", json={"text": "Send your OTP now", "language": "Hindi"})
assert r.status_code == 200 and r.json()["verdict"] == "HINDI-ANSWER" and _seen == ["Hindi"]
assert r.json()["trace"] == [] and r.json()["sources"] == []
# the agent returns its own fallback marker: also retried
m.run_agent = lambda case, ctx, lang="English": {"risk": "medium", "scam_type": "unclear", "verdict": "English fallback", "confidence": 0.0, "fallback": True}
r = c.post("/analyze/text", json={"text": "Send your OTP now", "language": "Hindi"})
assert r.json()["verdict"] == "HINDI-ANSWER"
# both fail: the translated safe sentence when it is cached, else the English one
def _fast_down(case, ctx, lang="English"):
    raise RuntimeError("down")
m.run_agent_fast = _fast_down
_labels._cache["Hindi"] = dict(_labels.ENGLISH_LABELS, safe_fallback="HINDI-SAFE")
assert c.post("/analyze/text", json={"text": "Send your OTP now", "language": "Hindi"}).json()["verdict"] == "HINDI-SAFE"
assert c.post("/analyze/text", json={"text": "Send your OTP now", "language": "Tamil"}).json()["verdict"] == _labels.ENGLISH_LABELS["safe_fallback"]
# labels route: known languages only
_labels._cache["Tamil"] = dict(_labels.ENGLISH_LABELS, why="TAMIL-WHY")
r = c.get("/api/labels", params={"language": "Tamil"})
assert r.status_code == 200 and r.json()["labels"]["why"] == "TAMIL-WHY"
assert c.get("/api/labels", params={"language": "Klingon"}).status_code == 400
assert c.get("/api/labels").json()["labels"]["why"] == "Why"
_labels._cache.clear(); _labels._cache["English"] = dict(_labels.ENGLISH_LABELS)

print("All API route tests passed.")
