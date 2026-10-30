"""Loads settings from the .env file so your keys never go into the code."""
import os
from dotenv import load_dotenv

load_dotenv()

MODEL_API_KEY = os.environ.get("MODEL_API_KEY", "")
MODEL_NAME = os.environ.get("MODEL_NAME", "muse-spark-1.3")
ASR_MODEL = os.environ.get("ASR_MODEL", "muse-voice-transcribe-1.0")
IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "muse-image-1.0")
AGENT_REASONING_EFFORT = os.environ.get("AGENT_REASONING_EFFORT", "low")
if AGENT_REASONING_EFFORT not in {"minimal", "low", "medium", "high", "xhigh", "max"}:
    raise ValueError("AGENT_REASONING_EFFORT must be a supported Muse reasoning level.")
BASE_URL = os.environ.get("BASE_URL", "https://api.meta.ai/v1")
ASR_URL = "https://api.meta.ai/v1/asr/transcribe"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "").lstrip("@")
# Optional, for slow or filtered networks. Defaults keep python-telegram-bot's own behaviour.
TELEGRAM_CONNECT_TIMEOUT = float(os.environ.get("TELEGRAM_CONNECT_TIMEOUT", "0") or 0)
TELEGRAM_PROXY = os.environ.get("TELEGRAM_PROXY", "")
DB_PATH = os.environ.get("DB_PATH", "data/scamshield.db")
# Speed setting: 1 = run fast mode (instant local link checks + single model call). 0 = full multi-turn tool-calling agent.
FAST_MODE = os.environ.get("FAST_MODE", "1") == "1"
BOT_FAST_MODE = os.environ.get("BOT_FAST_MODE", "1") == "1"
