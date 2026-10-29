"""Run:  python tests_offline.py
Tests the parts that do NOT need the internet: link checks, family store, SAM output parser, and the agent loop (with a fake model)."""
import json
import os
import struct
import tempfile
from types import SimpleNamespace as NS

from app import config
config.DB_PATH = os.path.join(tempfile.mkdtemp(), "test.db")

from app import agent, llm, store
from app.checks import check_url
from app.sam_refine import BOX_RE, _iou
from app import voice


def test_links():
    flags = check_url("http://paypa1-security.click/login")["flags"]
    assert any("paypal" in f for f in flags) and any(".click" in f for f in flags), flags
    assert check_url("https://www.paypal.com/signin")["flags"] == []


def test_links_country_domains():
    for ok in ("google.co.uk", "paypal.co.uk", "paypal.com.au", "amazon.co.in", "www.paypal.com"):
        assert check_url(f"https://{ok}/")["flags"] == [], ok
    for bad in ("paypal.com.evil.xyz", "paypal-secure.co.uk", "paypa1.co.uk", "paypal.tk", "amaz0n-help.com"):
        flags = check_url(f"https://{bad}/")["flags"]
        assert any("not the official" in f or "often used in scams" in f for f in flags), (bad, flags)


def test_store():
    store.upsert_user(1, "Granny")
    code = store.create_invite(1)
    assert store.accept_invite(2, "000000") is None
    assert store.accept_invite(2, code) == 1
    assert store.get_guardians(1) == [2]
    store.forget(1)
    assert store.get_guardians(1) == []


def test_join_attempt_limit():
    assert store.allow_join_attempt(20, limit=2)
    assert store.accept_invite(20, "bad-code") is None
    assert store.allow_join_attempt(20, limit=2)
    assert not store.allow_join_attempt(20, limit=2)
    store.forget(20)


def test_rate_limit_and_daily_count():
    store.upsert_user(10, "Test user")
    for _ in range(20):
        assert store.consume_check_quota(10, limit=20)
    assert not store.consume_check_quota(10, limit=20)
    store.log_event(10, "low", "none")
    assert store.get_checks_today(10) == 1
    store.forget(10)


def test_voice_errors():
    with tempfile.NamedTemporaryFile() as empty:
        try:
            voice.transcribe_file(empty.name, "English")
        except ValueError as e:
            assert "empty" in str(e).lower()
        else:
            raise AssertionError("empty audio should be rejected")

    try:
        voice._validate_language("Sinhala")
    except ValueError as e:
        assert "Sinhala" in str(e) and "Text and screenshots" in str(e)
    else:
        raise AssertionError("unsupported Sinhala voice should be rejected")

    original_run = voice.subprocess.run
    voice.subprocess.run = lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError())
    try:
        try:
            voice.to_wav("input.ogg", "output.wav")
        except RuntimeError as e:
            assert "ffmpeg" in str(e)
        else:
            raise AssertionError("missing ffmpeg should be reported")
    finally:
        voice.subprocess.run = original_run

    original_convert = voice.to_wav
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + (14_424_000 * 2), b"WAVE", b"fmt ", 16,
        1, 1, 24000, 48000, 2, 16, b"data", 14_424_000 * 2,
    )
    def write_long_header(_src, dst):
        with open(dst, "wb") as target:
            target.write(header)

    voice.to_wav = write_long_header
    try:
        with tempfile.NamedTemporaryFile() as audio:
            audio.write(b"synthetic audio")
            audio.flush()
            try:
                voice.transcribe_file(audio.name, "English")
            except ValueError as e:
                assert "10 minutes" in str(e)
            else:
                raise AssertionError("audio longer than ten minutes should be rejected")
    finally:
        voice.to_wav = original_convert


def test_sam_parser():
    line = "<0f>0<|box;x1=10;y1=20;x2=110;y2=120;w=200;h=400|><|mask;x=0;y=0;data=1,1,~a|>"
    m = BOX_RE.search(line)
    assert m and m.group(1) == "10" and m.group(6) == "400"
    assert abs(_iou([0, 0, .5, .5], [0, 0, .5, .5]) - 1) < 1e-9


class FakeClient:
    """Pretends to be Muse Spark: first asks for two tools, then gives the final JSON."""
    def __init__(self):
        self.calls = 0
        self.responses = NS(create=self.create)

    def create(self, **kw):
        self.calls += 1
        if self.calls == 1:
            return NS(id="r1", output_text="", output=[
                NS(type="function_call", name="check_links", arguments=json.dumps({"text": "go to http://bit.ly/x"}), call_id="c1"),
                NS(type="function_call", name="alert_trusted_person", arguments=json.dumps({"risk": "high", "scam_type": "prize_lottery", "reason": "Asks for a fee."}), call_id="c2"),
            ])
        assert kw["previous_response_id"] == "r1"
        assert {o["call_id"] for o in kw["input"]} == {"c1", "c2"}
        return NS(id="r2", output=[], output_text=json.dumps({"risk": "high", "scam_type": "prize", "verdict": "Likely scam.", "reasons": ["fee"], "red_flags": ["bit.ly"], "next_step": "Ignore it.", "confidence": 0.9}))


def test_agent_loop():
    agent.get_client = lambda: FakeClient()
    ctx = agent.AgentContext(elder_id=1, has_guardians=True)
    result = agent.run_agent("You won! pay fee http://bit.ly/x", ctx, "English")
    assert result["risk"] == "high"
    assert len(ctx.alerts) == 1 and "Checked 1 link(s)" in result["actions"]


def test_agent_bad_args():
    ctx = agent.AgentContext()
    assert "error" in agent._execute("check_links", "not json", ctx)
    assert "error" in agent._execute("nope", "{}", ctx)
    assert agent._execute("alert_trusted_person", json.dumps({"risk": "high", "scam_type": "x", "reason": "y"}), ctx)["sent"] is False


def test_structured_output_malformed_response():
    class MalformedClient:
        responses = NS(create=lambda **kwargs: NS(output_text="not JSON"))

    original = llm.get_client
    llm.get_client = lambda: MalformedClient()
    try:
        try:
            llm._ask("test", "rules")
        except ValueError:
            pass
        else:
            raise AssertionError("malformed structured output should be rejected")
    finally:
        llm.get_client = original


def test_structured_output_schema_and_reasoning():
    captured = {}
    payload = {
        "risk": "low", "scam_type": "none", "verdict": "Looks safe.", "reasons": [],
        "red_flags": [], "next_step": "No action needed.", "confidence": 0.9,
    }

    class ValidClient:
        responses = NS(create=lambda **kwargs: (captured.update(kwargs) or NS(output_text=json.dumps(payload))))

    original = llm.get_client
    llm.get_client = lambda: ValidClient()
    try:
        result = llm._ask("test", "rules", reasoning_effort="low")
        assert result["risk"] == "low"
        assert captured["text"]["format"]["type"] == "json_schema"
        assert captured["text"]["format"]["strict"] is True
        assert captured["reasoning"] == {"effort": "low"}
    finally:
        llm.get_client = original


class ScenarioClient:
    def __init__(self, final, tool_calls):
        self.final = final
        self.tool_calls = tool_calls
        self.calls = 0
        self.responses = NS(create=self.create)

    def create(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return NS(id="scenario-1", output_text="", output=self.tool_calls)
        assert kwargs["previous_response_id"] == "scenario-1"
        return NS(id="scenario-2", output=[], output_text=json.dumps(self.final))


def _function_call(name, call_id, arguments):
    return NS(type="function_call", name=name, call_id=call_id, arguments=json.dumps(arguments))


def test_agent_risk_alert_guardrails():
    risky_final = {
        "risk": "high", "scam_type": "fake payment", "verdict": "Do not pay.",
        "reasons": ["Asks for money."], "red_flags": ["pay now"],
        "next_step": "Ignore it.", "confidence": 0.9, "sources": [],
    }
    low_final = {
        "risk": "low", "scam_type": "none", "verdict": "This looks safe.",
        "reasons": ["No suspicious request."], "red_flags": [],
        "next_step": "Use your usual app.", "confidence": 0.9, "sources": [],
    }
    alert_calls = [
        _function_call("alert_trusted_person", "a1", {"risk": "high", "scam_type": "scam", "reason": "Review this."}),
        _function_call("alert_trusted_person", "a2", {"risk": "high", "scam_type": "scam", "reason": "Review this."}),
    ]

    for i in range(10):
        ctx = agent.AgentContext(elder_id=i, has_guardians=True)
        agent.get_client = lambda: ScenarioClient(risky_final, alert_calls)
        result = agent.run_agent(f"Please send money now, fake case {i}", ctx)
        assert result["risk"] == "high" and len(ctx.alerts) == 1

    for i in range(5):
        ctx = agent.AgentContext(elder_id=i, has_guardians=True)
        agent.get_client = lambda: ScenarioClient(low_final, alert_calls)
        result = agent.run_agent(f"Appointment reminder, safe case {i}", ctx)
        assert result["risk"] == "low" and not ctx.alerts
        assert "Alert queued for trusted person" not in result["actions"]

    ctx = agent.AgentContext(elder_id=99, has_guardians=False)
    agent.get_client = lambda: ScenarioClient(risky_final, alert_calls)
    result = agent.run_agent("Please send money now.", ctx)
    assert not ctx.alerts and "/guardian" in result["next_step"]

    safe_medium_ctx = agent.AgentContext(has_guardians=True, case_text="The reminder says do not send money or share your code.")
    sent = agent._tool_alert(
        {"risk": "medium", "scam_type": "unclear", "reason": "No action is requested."},
        safe_medium_ctx,
    )
    assert sent["sent"] is False and not safe_medium_ctx.alerts
    requested_ctx = agent.AgentContext(has_guardians=True, case_text="The caller says pay the fee to claim a prize.")
    sent = agent._tool_alert(
        {"risk": "medium", "scam_type": "prize_lottery", "reason": "Pay a fee."},
        requested_ctx,
    )
    assert sent["sent"] is True and len(requested_ctx.alerts) == 1


def test_agent_sources_and_turn_limit():
    final = {
        "risk": "low", "scam_type": "none", "verdict": "Looks safe.", "reasons": [],
        "red_flags": [], "next_step": "Use your usual app.", "confidence": 0.9, "sources": [],
    }
    citation = NS(type="url_citation", title="Example source", url="https://example.org/source")
    block = NS(annotations=[citation])
    search_response = NS(
        id="search-response",
        output_text=json.dumps(final),
        output=[NS(type="web_search_call"), NS(type="message", content=[block])],
    )
    agent.get_client = lambda: NS(responses=NS(create=lambda **kwargs: search_response))
    result = agent.run_agent("Verify a website.", agent.AgentContext())
    assert result["sources"] == [{"title": "Example source", "url": "https://example.org/source"}]
    assert result["actions"] == ["Searched the web for verification"]

    search_response.output = [
        NS(type="web_search_call", results=[{"title": "Search result", "url": "https://example.org/result"}])
    ]
    result = agent.run_agent("Verify a website.", agent.AgentContext())
    assert result["sources"] == [{"title": "Search result", "url": "https://example.org/result"}]

    class EndlessToolClient:
        def __init__(self):
            self.calls = 0
            self.responses = NS(create=self.create)

        def create(self, **kwargs):
            self.calls += 1
            return NS(
                id=f"response-{self.calls}",
                output_text="",
                output=[_function_call("scam_playbook", f"call-{self.calls}", {"scam_type": "delivery"})],
            )

    client = EndlessToolClient()
    agent.get_client = lambda: client
    result = agent.run_agent("A package message.", agent.AgentContext())
    assert client.calls == agent.MAX_TURNS
    assert "Stopped after the tool-call limit" in result["actions"]
def test_annotate_and_box_normalization():
    from io import BytesIO
    from PIL import Image, ImageChops
    from app.annotate import normalize_box, normalize_box_fractions, draw_regions_png

    # Test fraction boxes (0..1)
    nb = normalize_box([0.1, 0.2, 0.4, 0.5], 800, 600)
    assert nb == [80.0, 120.0, 320.0, 300.0]

    # Test 0..1000 scale boxes
    nb_1000 = normalize_box([100, 200, 400, 500], 800, 600)
    assert nb_1000 == [80.0, 120.0, 320.0, 300.0]

    # Test fractions helper
    frac = normalize_box_fractions([100, 200, 400, 500], 800, 600)
    assert abs(frac[0] - 0.1) < 1e-4 and abs(frac[3] - 0.5) < 1e-4

    # Test pixel scale boxes
    nb_pix = normalize_box([150, 400, 1050, 1800], 1080, 1920)
    assert nb_pix == [150.0, 400.0, 1050.0, 1800.0]

    # Test that draw_regions_png marks the expected area, not just the corner
    blank = Image.new("RGB", (800, 600), "#ffffff")
    buf = BytesIO()
    blank.save(buf, format="PNG")
    marked = draw_regions_png(buf.getvalue(), [{"box": [100, 200, 400, 500], "label": "test"}])
    marked_img = Image.open(BytesIO(marked))
    diff = ImageChops.difference(blank, marked_img)
    bbox = diff.getbbox()
    assert bbox is not None
    # Marked area must span the box [80, 120, 320, 300]
    assert bbox[0] <= 80 and bbox[1] <= 120 and bbox[2] >= 320 and bbox[3] >= 300


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK ", name)
    print("All offline tests passed.")
