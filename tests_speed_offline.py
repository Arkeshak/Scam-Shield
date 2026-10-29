"""Run:  python tests_speed_offline.py
Proves the speed fixes WITHOUT the internet: one model call in fast mode, parallel SAM calls, smaller photos."""
import io
import json
import time
from types import SimpleNamespace as NS

from PIL import Image

from app import agent, annotate, sam_refine


class CountingClient:
    def __init__(self, payload):
        self.calls, self.payload = 0, payload
        self.responses = NS(create=self.create)

    def create(self, **kw):
        self.calls += 1
        assert "tools" not in kw, "fast mode must not use the tool loop"
        return NS(id="r", output=[], output_text=json.dumps(self.payload))


def test_fast_mode_one_call():
    payload = {"risk": "high", "scam_type": "prize", "verdict": "Likely scam.", "reasons": ["fee"], "red_flags": ["bit.ly"], "next_step": "Ignore it.", "confidence": 0.9}
    client = CountingClient(payload)
    agent.get_client = lambda: client
    ctx = agent.AgentContext(elder_id=1, has_guardians=True)
    result = agent.run_agent_fast("You won! Pay at http://bit.ly/x77", ctx, "English")
    assert client.calls == 1, client.calls
    assert result["risk"] == "high" and len(ctx.alerts) == 1
    assert "Checked 1 link(s)" in result["actions"] and "Alert queued for trusted person" in result["actions"]
    low = CountingClient({**payload, "risk": "low"})
    agent.get_client = lambda: low
    ctx2 = agent.AgentContext(elder_id=1, has_guardians=True)
    agent.run_agent_fast("Hi, dentist at 3 PM.", ctx2, "English")
    assert ctx2.alerts == [], "no alert for low risk"


def test_fast_mode_bad_json():
    agent.get_client = lambda: CountingClient({}) if False else NS(responses=NS(create=lambda **kw: NS(id="r", output=[], output_text="not json at all")))
    result = agent.run_agent_fast("hello", agent.AgentContext(), "English")
    assert result["risk"] == "medium" and "could not finish" in result["verdict"].lower()


def test_sam_runs_in_parallel():
    def slow(image_bytes, mime, concept):
        time.sleep(0.4)
        return [{"box": [0.1, 0.1, 0.3, 0.3]}]
    sam_refine.segment_concept = slow
    regions = [{"label": n, "sam_prompt": n, "box": [0.1, 0.1, 0.3, 0.3]} for n in ("logo", "button", "link", "phone")]
    t = time.time()
    out = sam_refine.refine_with_sam(b"x", "image/png", regions)
    elapsed = time.time() - t
    assert elapsed < 1.0, f"4 SAM calls took {elapsed:.2f}s, they should overlap (about 0.4s)"
    assert len(out) == 4 and all(r["source"] == "sam-3.1" for r in out)
    assert len(sam_refine.refine_with_sam(b"x", "image/png", regions * 3)) == sam_refine.MAX_REGIONS


def test_sam_failure_keeps_rough_box():
    def boom(image_bytes, mime, concept):
        raise RuntimeError("down")
    sam_refine.segment_concept = boom
    out = sam_refine.refine_with_sam(b"x", "image/png", [{"label": "logo", "box": [0, 0, 0.5, 0.5]}])
    assert out[0]["source"] == "muse" and out[0]["box"] == [0, 0, 0.5, 0.5]


def test_shrink_image():
    big = io.BytesIO()
    Image.new("RGB", (3000, 2000), (200, 30, 30)).save(big, format="PNG")
    data, mime = annotate.shrink_image(big.getvalue())
    img = Image.open(io.BytesIO(data))
    assert mime == "image/jpeg" and max(img.size) == 1024 and len(data) < len(big.getvalue())


def test_bot_imports_and_flags():
    import app.bot as bot
    from app import config
    assert hasattr(bot, "Stages") and hasattr(bot, "safe_edit") and config.BOT_FAST_MODE in (True, False)
    assert hasattr(bot, "_send_comparison_card_later"), "comparison card helper must be importable"


def test_comparison_card_structure():
    """make_comparison_card calls Muse Image; mock it and check the Pillow overlay runs without error."""
    import io as _io
    from PIL import Image as _Image
    from app import cards, config

    fake_png = _io.BytesIO()
    _Image.new("RGB", (512, 512), (30, 30, 100)).save(fake_png, format="PNG")

    class FakeImages:
        def generate(self, **kw):
            import base64 as b64
            from types import SimpleNamespace as _NS
            return _NS(data=[_NS(b64_json=b64.b64encode(fake_png.getvalue()).decode())])

    original_client = cards.get_client
    cards.get_client = lambda: type("C", (), {"images": FakeImages()})()
    try:
        result = cards.make_comparison_card("fake bank SMS", ["Suspicious link", "Asks for OTP"])
        assert result is not None, "comparison card must return bytes"
        img = _Image.open(_io.BytesIO(result))
        assert img.width == 512 and img.height > 512, "card must be taller than the art (bar added below)"
    finally:
        cards.get_client = original_client


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK ", name)
    print("All speed tests passed.")
