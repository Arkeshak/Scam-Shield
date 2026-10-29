"""Scam CALL analyzer: Muse Voice Transcribe (speaker labels) + Muse Spark.
Upload a recorded call -> who said what -> which lines are pressure tricks."""
import json

from . import config
from .llm import _extract_json, _json_schema, get_client
from .voice import transcribe_turns

CALL_RULES = """You are ScamShield, checking a recorded phone call for scams.
The call is split into numbered turns with speaker labels (A, B...). Speaker labels are not names.
Use very simple words. Never say you are 100% sure. Reply with JSON only, no markdown fences."""

CALL_SHAPE = """{
  "risk": "low" | "medium" | "high",
  "scam_type": "short name or 'none'",
  "verdict": "one simple sentence",
  "reasons": ["simple reason"],
  "flagged_turns": [{"turn": 3, "trick": "what trick this line uses, e.g. urgency, secrecy, asks for code"}],
  "next_step": "one clear action",
  "confidence": number from 0 to 1
}"""

CALL_SCHEMA = {
    "type": "object",
    "properties": {
        "risk": {"type": "string", "enum": ["low", "medium", "high"]},
        "scam_type": {"type": "string"},
        "verdict": {"type": "string"},
        "reasons": {"type": "array", "items": {"type": "string"}},
        "flagged_turns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "turn": {"type": "integer"},
                    "trick": {"type": "string"},
                },
                "required": ["turn", "trick"],
                "additionalProperties": False,
            },
        },
        "next_step": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["risk", "scam_type", "verdict", "reasons", "flagged_turns", "next_step", "confidence"],
    "additionalProperties": False,
}


from .timing import Timings


def analyze_call(path: str, language: str = "English", timings: Timings | None = None) -> dict:
    t = timings or Timings()
    with t.step("Separate speakers", "Muse Voice Transcribe"):
        data = transcribe_turns(path, language)
    turns = data["turns"]
    if turns:
        numbered = "\n".join(f"[{t_item.get('turnId')}] Speaker {t_item.get('speaker', '?')}: {t_item.get('transcript', '')}" for t_item in turns)
    else:
        numbered = data["transcript"]
    if not numbered.strip():
        res = {"risk": "low", "scam_type": "none", "verdict": "I could not hear any words.", "reasons": [], "flagged_turns": [],
               "next_step": "Try a clearer recording.", "confidence": 0.0, "turns": [], "transcript": ""}
        res.update(t.summary())
        return res

    prompt = f"CALL TRANSCRIPT:\n{numbered}\n\nWrite all text fields in {language}.\nReturn JSON in this shape:\n{CALL_SHAPE}"
    with t.step("Find pressure tricks", "Muse Spark"):
        response = get_client().responses.create(
            model=config.MODEL_NAME,
            instructions=CALL_RULES,
            input=[{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            text=_json_schema("call_analysis", CALL_SCHEMA),
        )
    try:
        result = json.loads(response.output_text)
    except (TypeError, json.JSONDecodeError):
        result = _extract_json(response.output_text)
    if not isinstance(result, dict) or result.get("risk") not in {"low", "medium", "high"}:
        raise ValueError("Model returned an invalid structured call analysis")
    result["turns"] = turns
    result["transcript"] = data["transcript"]
    result.update(t.summary())
    return result
