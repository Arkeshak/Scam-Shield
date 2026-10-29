"""ScamShield Family API and web application.
Run: uvicorn app.main:app --reload
Open: http://127.0.0.1:8000
"""
import asyncio
import base64
import json
import logging
import os
import tempfile
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import call, config, guard, llm, store
from .agent import AgentContext, run_agent
from .annotate import draw_regions, shrink_image
from .cards import make_comparison_card
from .checks import check_all_links
from .sam_refine import refine_with_sam
from .voice import transcribe_file

log = logging.getLogger(__name__)
app = FastAPI(title="ScamShield Family")
ROOT = Path(__file__).resolve().parent.parent
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

MAX_UPLOAD_BYTES = 32 * 1024 * 1024
MAX_MESSAGE_CHARS = 10000
MAX_IMAGE_PIXELS = 16_000_000


class TextIn(BaseModel):
    text: str = Field(max_length=MAX_MESSAGE_CHARS)
    language: str = "English"


class ComparisonCardIn(BaseModel):
    scam_type: str = Field(default="Suspicious Scam", max_length=120)
    red_flags: list[str] = Field(default_factory=list, max_length=4)


def _read_upload(data: bytes):
    if not data:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Files must be 32 MB or smaller.")


def _validate_image(data: bytes, mime: str) -> str:
    try:
        image = Image.open(BytesIO(data))
        if image.format not in {"PNG", "JPEG", "WEBP"}:
            raise HTTPException(400, "Please upload a PNG, JPEG, or WebP screenshot.")
        if image.width * image.height > MAX_IMAGE_PIXELS:
            raise HTTPException(413, "Screenshots must be 16 megapixels or smaller.")
        image.verify()
        return Image.MIME.get(image.format, mime)
    except HTTPException:
        raise
    except Exception as e:  # UnidentifiedImageError, OSError, SyntaxError, struct.error, etc.
        raise HTTPException(400, "The uploaded file is not a valid supported image.") from e


from .timing import Timings


def _analyze_message(text: str, language: str, timings: Timings | None = None) -> dict:
    t = timings or Timings()
    link_checks = check_all_links(text)  # always runs locally, never fails
    try:
        with t.step("Agent checks", "Muse Spark"):
            result = run_agent(text, AgentContext(has_guardians=False), language)
    except Exception:
        log.exception("Agent call failed; returning safe fallback")
        result = {
            "risk": "medium",
            "scam_type": "unclear",
            "verdict": "I could not finish the check. Please do not click, pay, or share codes. Ask someone you trust.",
            "reasons": [],
            "red_flags": [],
            "next_step": "Ask a family member or call your bank using the number on your card.",
            "confidence": 0.0,
            "actions": [],
            "trace": [],
            "sources": [],
        }
    result["link_checks"] = link_checks
    result.update(t.summary())
    return result


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/analyze/text")
async def analyze_text(body: TextIn):
    if not body.text.strip():
        raise HTTPException(400, "Text is empty.")
    try:
        t = Timings()
        return await asyncio.to_thread(_analyze_message, body.text, body.language, t)
    except Exception as e:
        log.exception("Text analysis failed")
        raise HTTPException(502, "Text analysis is unavailable. Please try again.") from e


@app.post("/analyze/image")
async def analyze_image(file: UploadFile = File(...), language: str = Form("English")):
    try:
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        _read_upload(data)
        mime = file.content_type or "image/png"
        mime = _validate_image(data, mime)
        small_data, small_mime = shrink_image(data)
        t = Timings()
        with t.step("Read the screenshot", "Muse Spark"):
            result = await asyncio.to_thread(llm.analyze_image, small_data, small_mime, language)
        with t.step("Outline fake parts", "SAM 3.1"):
            regions = await asyncio.to_thread(refine_with_sam, small_data, small_mime, result.get("regions", []))
        result["regions"] = regions
        result["marked_image"] = draw_regions(data, regions)
        result["sources"] = []
        result.update(t.summary())
        return result
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Screenshot analysis failed")
        raise HTTPException(502, "Screenshot analysis is unavailable. Please try again.") from e
    finally:
        await file.close()


async def _write_upload(upload: UploadFile) -> str:
    temp = None
    try:
        data = await upload.read(MAX_UPLOAD_BYTES + 1)
        _read_upload(data)
        temp = tempfile.NamedTemporaryFile(prefix="scamshield-", suffix=".audio", delete=False)
        temp.write(data)
        temp.close()
        return temp.name
    except Exception:
        if temp is not None:
            temp.close()
            os.unlink(temp.name)
        raise
    finally:
        await upload.close()


@app.post("/analyze/voice")
async def analyze_voice(file: UploadFile = File(...), language: str = Form("English")):
    path = await _write_upload(file)
    try:
        t = Timings()
        with t.step("Transcribe voice", "Muse Voice Transcribe"):
            transcript = await asyncio.to_thread(transcribe_file, path, language)
        if not transcript:
            raise HTTPException(422, "No speech was detected. Try a clearer recording.")
        result = await asyncio.to_thread(_analyze_message, f"Voice note transcript:\n{transcript}", language, t)
        result["transcript"] = transcript
        return result
    except HTTPException:
        raise
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        log.exception("Voice analysis failed")
        raise HTTPException(502, "Voice analysis is unavailable. Please try again.") from e
    finally:
        os.unlink(path)


@app.post("/analyze/call")
async def analyze_call(file: UploadFile = File(...), language: str = Form("English")):
    path = await _write_upload(file)
    try:
        t = Timings()
        return await asyncio.to_thread(call.analyze_call, path, language, t)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        log.exception("Call analysis failed")
        raise HTTPException(502, "Call analysis is unavailable. Please try again.") from e
    finally:
        os.unlink(path)


@app.post("/api/comparison_card")
async def generate_comparison_card(body: ComparisonCardIn):
    try:
        t = Timings()
        with t.step("Real vs Scam comparison card", "Muse Image"):
            card_bytes = await asyncio.to_thread(make_comparison_card, body.scam_type, body.red_flags)
        if not card_bytes:
            raise HTTPException(502, "Could not generate comparison card illustration.")
        b64 = base64.b64encode(card_bytes).decode("utf-8")
        res = {
            "card": f"data:image/png;base64,{b64}",
            "scam_type": body.scam_type,
            "red_flags": body.red_flags,
        }
        res.update(t.summary())
        return res
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Comparison card generation failed")
        raise HTTPException(502, "Comparison card generation is unavailable. Please try again.") from e


@app.get("/api/metrics")
def metrics():
    dev_path = ROOT / "data" / "eval_results.json"
    heldout_path = ROOT / "data" / "eval_heldout.json"
    screens_path = ROOT / "data" / "eval_screenshots.json"

    dev_data = json.loads(dev_path.read_text(encoding="utf-8")) if dev_path.is_file() else {}
    heldout_data = json.loads(heldout_path.read_text(encoding="utf-8")) if heldout_path.is_file() else {}
    screens_data = json.loads(screens_path.read_text(encoding="utf-8")) if screens_path.is_file() else dev_data.get("screenshot_evaluation", {})

    return {
        "development": dev_data,
        "unseen": heldout_data,
        "screenshot_evaluation": screens_data,
        "n": dev_data.get("n", 0),
        "accuracy": dev_data.get("accuracy", 0),
        "false_alarms": dev_data.get("false_alarms", 0),
        "missed_scams": dev_data.get("missed_scams", 0),
        "worst_cases": dev_data.get("worst_cases", []),
    }


@app.get("/api/config")
def public_config():
    return {
        "models": {
            "spark": config.MODEL_NAME,
            "sam": "sam-3.1",
            "voice": config.ASR_MODEL,
            "image": config.IMAGE_MODEL,
            "reasoning": config.MODEL_NAME,
            "segmentation": "sam-3.1",
            "speech": config.ASR_MODEL,
        },
        "bot_username": config.TELEGRAM_BOT_USERNAME or None,
    }


@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse((ROOT / "static" / "index.html").read_text(encoding="utf-8"))


@app.get("/guard", response_class=HTMLResponse)
def guard_page():
    return HTMLResponse((ROOT / "static" / "guard.html").read_text(encoding="utf-8"))


@app.websocket("/ws/guard")
async def ws_guard(websocket: WebSocket):
    await websocket.accept()
    await guard.run_guard_session(websocket)

