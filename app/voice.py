"""Voice notes -> text with Muse Voice Transcribe.
The API accepts mono 16-bit PCM WAV files, so ffmpeg converts uploaded audio first.
"""
import json
import os
import subprocess
import tempfile
import wave

import requests

from . import config

VOICE_LANGUAGES = {
    "Arabic", "Bengali", "Dutch", "English", "French", "German", "Hebrew", "Hindi", "Indonesian",
    "Italian", "Japanese", "Kannada", "Korean", "Malay", "Mandarin Chinese", "Marathi", "Polish",
    "Portuguese", "Spanish", "Tagalog", "Tamil", "Telugu", "Thai", "Turkish", "Vietnamese",
}
MAX_AUDIO_BYTES = 32 * 1024 * 1024
MAX_AUDIO_SECONDS = 10 * 60


def to_wav(src_path: str, dst_path: str):
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", src_path, "-ac", "1", "-ar", "24000",
                "-c:a", "pcm_s16le", "-map_metadata", "-1", dst_path,
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
    except FileNotFoundError as e:
        raise RuntimeError("Audio conversion is unavailable because ffmpeg is not installed.") from e
    except subprocess.CalledProcessError as e:
        raise ValueError("This audio file could not be decoded. Please try a different recording.") from e
    except subprocess.TimeoutExpired as e:
        raise ValueError("Audio conversion took too long. Please try a shorter recording.") from e


def _validate_language(language: str | None):
    if language and language not in VOICE_LANGUAGES:
        raise ValueError(
            f"Voice transcription does not support {language} yet. Text and screenshots still work."
        )


def _transcribe(path: str, language: str | None, mode: str) -> dict:
    if mode not in {"PUSH_TO_TALK", "DIARIZATION"}:
        raise ValueError("Unsupported transcription mode.")
    _validate_language(language)
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        raise ValueError("The audio recording is empty.")

    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "audio.wav")
        to_wav(path, wav)
        if os.path.getsize(wav) > MAX_AUDIO_BYTES:
            raise ValueError("Audio files must be 32 MB or smaller after conversion.")
        try:
            with wave.open(wav, "rb") as audio:
                duration = audio.getnframes() / audio.getframerate()
        except (wave.Error, ZeroDivisionError) as e:
            raise ValueError("The converted audio file is not a valid WAV recording.") from e
        if duration > MAX_AUDIO_SECONDS:
            raise ValueError("Audio recordings must be 10 minutes or shorter.")

        request = {"mode": mode, "model": config.ASR_MODEL, "audioEncoding": "WAV"}
        if language:
            request["languageBias"] = [language]
        with open(wav, "rb") as audio:
            response = requests.post(
                config.ASR_URL,
                headers={"Authorization": f"Bearer {config.MODEL_API_KEY}", "Accept": "application/json"},
                files={
                    "request": (None, json.dumps(request), "application/json"),
                    "audio": ("audio.wav", audio, "audio/wav"),
                },
                timeout=120,
            )
        response.raise_for_status()
        result = response.json()

    if not isinstance(result, dict) or not isinstance(result.get("transcript"), str):
        raise ValueError("The transcription service returned an invalid response.")
    if not isinstance(result.get("turns", []), list):
        raise ValueError("The transcription service returned invalid speaker turns.")
    return result


def transcribe_file(path: str, language: str | None = None) -> str:
    """Transcribe one voice note in PUSH_TO_TALK mode."""
    return _transcribe(path, language, "PUSH_TO_TALK")["transcript"].strip()


def transcribe_turns(path: str, language: str | None = None) -> dict:
    """Transcribe a call with speaker diarization."""
    return _transcribe(path, language, "DIARIZATION")
