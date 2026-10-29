"""All calls to the Meta Model API live here."""
import base64
import json
import re

from openai import OpenAI

from . import config
from .checks import check_all_links

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        if not config.MODEL_API_KEY:
            raise RuntimeError("MODEL_API_KEY is not set. Put it in your .env file.")
        _key = config.MODEL_API_KEY
        _client = OpenAI(base_url=config.BASE_URL, api_key=_key, timeout=30.0, max_retries=1)
    return _client


RESULT_SHAPE = """{
  "risk": "low" | "medium" | "high",
  "scam_type": "short name, e.g. fake bank SMS, delivery link, prize scam, or 'none'",
  "verdict": "one simple sentence",
  "reasons": ["simple reason 1", "simple reason 2"],
  "red_flags": ["exact words or items that look fake"],
  "next_step": "one clear action the person should take",
  "confidence": number from 0 to 1
}"""

RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "risk": {"type": "string", "enum": ["low", "medium", "high"]},
        "scam_type": {"type": "string"},
        "verdict": {"type": "string"},
        "reasons": {"type": "array", "items": {"type": "string"}},
        "red_flags": {"type": "array", "items": {"type": "string"}},
        "next_step": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["risk", "scam_type", "verdict", "reasons", "red_flags", "next_step", "confidence"],
    "additionalProperties": False,
}

IMAGE_RESULT_SCHEMA = {
    **RESULT_SCHEMA,
    "properties": {
        **RESULT_SCHEMA["properties"],
        "regions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "reason": {"type": "string"},
                    "sam_prompt": {"type": "string"},
                    "box": {"type": "array", "items": {"type": "number"}},
                },
                "required": ["label", "reason", "sam_prompt", "box"],
                "additionalProperties": False,
            },
        },
    },
    "required": RESULT_SCHEMA["required"] + ["regions"],
}


def _json_schema(name: str, schema: dict) -> dict:
    return {
        "format": {
            "type": "json_schema",
            "name": name,
            "strict": True,
            "schema": schema,
        }
    }


RULES = """You are ScamShield, a careful scam checker that protects ordinary people, especially elders.
Rules:
- Use very simple words. Short sentences.
- Never say you are 100% sure. If unsure, say so and tell the person to ask someone they trust.
- Never tell the person to click links, call numbers in the message, or share codes.
- If the message is normal and safe, say risk is "low" and explain why.
- Reply with JSON only. No extra text, no markdown fences."""


def _extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Model did not return JSON: " + text[:200])
    return json.loads(text[start : end + 1])


def _ask(
    content,
    instructions: str,
    schema: dict = RESULT_SCHEMA,
    schema_name: str = "scam_analysis",
    reasoning_effort: str | None = None,
) -> dict:
    request = dict(
        model=config.MODEL_NAME,
        instructions=instructions,
        input=[{"role": "user", "content": content}],
        text=_json_schema(schema_name, schema),
    )
    if reasoning_effort:
        request["reasoning"] = {"effort": reasoning_effort}
    response = get_client().responses.create(**request)
    try:
        result = json.loads(response.output_text)
    except (TypeError, json.JSONDecodeError):
        result = _extract_json(response.output_text)
    if not isinstance(result, dict) or result.get("risk") not in {"low", "medium", "high"}:
        raise ValueError("Model returned an invalid structured scam analysis")
    required = schema["required"]
    if any(key not in result for key in required):
        raise ValueError("Model structured response is missing required fields")
    return result


def analyze_text(text: str, language: str = "English", reasoning_effort: str | None = None) -> dict:
    links = check_all_links(text)
    prompt = (
        f"Check this message for scams.\n\nMESSAGE:\n{text}\n\n"
        f"LINK CHECK RESULTS (from our own tool):\n{json.dumps(links, ensure_ascii=False)}\n\n"
        f"Write all text fields in {language}.\n"
        f"Return JSON in this shape:\n{RESULT_SHAPE}"
    )
    result = _ask([{"type": "input_text", "text": prompt}], RULES, reasoning_effort=reasoning_effort)
    result["link_checks"] = links
    return result


def analyze_image(image_bytes: bytes, mime: str, language: str = "English") -> dict:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    shape = RESULT_SHAPE.rstrip("}") + """,
  "regions": [
    {"label": "short name", "reason": "why it looks fake",
     "sam_prompt": "1-3 word UI element + color, e.g. 'red button', 'dark header bar', 'blue link'",
     "box": [x1, y1, x2, y2]}
  ]
}"""
    prompt = (
        "Look at this screenshot (SMS, email, chat, social media, or website). Check it for scams.\n"
        "IMPORTANT: If there are ANY suspicious elements, red flags, or scam tricks (such as suspicious message text, "
        "SMS message bubble, urgent payment request, fake sender ID, contact number, suspicious link, fraudulent button, "
        "or fake logo), you MUST identify the regions and provide bounding boxes so we can highlight them on the image.\n"
        "For each suspicious area, include:\n"
        "- label: short name of what this element is (e.g. 'fake parcel message', 'suspicious link', 'fake urgency text')\n"
        "- reason: why it looks fake or risky\n"
        "- sam_prompt: EXACTLY 1-3 words naming the visible UI element type and its dominant color. "
        "Describe the SHAPE/WIDGET, not the text content. "
        "Good examples: 'red button', 'dark header bar', 'blue link', 'white card', 'warning badge'. "
        "Bad examples (too long, mentions content): 'text saying you won money'. "
        "For each suspicious region, always try to name the outermost clickable or colored element.\n"
        "- box: bounding box as fractions from 0.0 to 1.0: [left, top, right, bottom] (where 0,0 is top-left and 1,1 is bottom-right)\n"
        f"Write label, reason, and text explanations in {language} (sam_prompt must remain in English).\n"
        f"Return JSON in this shape:\n{shape}"
    )
    content = [
        {"type": "input_text", "text": prompt},
        {"type": "input_image", "image_url": f"data:{mime};base64,{b64}"},
    ]
    return _ask(content, RULES, IMAGE_RESULT_SCHEMA, "screenshot_analysis")
