"""Generate 6 synthetic test calls (3 scam, 3 safe) using Windows System.Speech.
All audio is labeled synthetic.
"""
import os
import subprocess
from pathlib import Path

OUT_DIR = Path("data/synthetic_calls")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CALLS = [
    {
        "id": "call_01_synthetic_bank_otp",
        "label": "scam",
        "trick": "code, secrecy, urgency",
        "text": "Hello. This is the fraud prevention department at your bank. We detected an unauthorized payment. To stop this transaction immediately, please read me the six digit one time passcode sent to your phone right now. Keep this secret and do not hang up.",
    },
    {
        "id": "call_02_synthetic_police_warrant",
        "label": "scam",
        "trick": "police threat, gift card, urgency",
        "text": "This is Officer Miller from the federal police task force. There is an urgent warrant for your arrest due to unpaid federal taxes. You must resolve this immediately using a wire transfer or gift card right now, or our officers will come to your home within the hour.",
    },
    {
        "id": "call_03_synthetic_remote_support",
        "label": "scam",
        "trick": "remote access, AnyDesk",
        "text": "Hello, this is urgent customer support. Your computer is transmitting multiple dangerous viruses. You need to download AnyDesk or TeamViewer immediately and read me your nine digit access code so I can take control and clean your computer.",
    },
    {
        "id": "call_04_synthetic_clinic_appointment",
        "label": "safe",
        "trick": "none",
        "text": "Hello, this is City Medical Clinic calling to confirm your routine dental checkup tomorrow at three o'clock in the afternoon. Please remember to arrive ten minutes early. If you need to reschedule, call our reception. Have a nice day.",
    },
    {
        "id": "call_05_synthetic_delivery_notice",
        "label": "safe",
        "trick": "none",
        "text": "Hello, this is the courier delivery service. We have safely left your parcel at the front doorstep next to the planter. No signature is required. Thank you and have a good day.",
    },
    {
        "id": "call_06_synthetic_family_chat",
        "label": "safe",
        "trick": "none",
        "text": "Hi Grandma, it's Alex! Just calling to see how you are feeling and if you would like to come over for dinner this Sunday. Mom is making your favorite vegetable soup. Give me a call whenever you are free, love you!",
    },
]


def generate():
    for c in CALLS:
        raw_wav = OUT_DIR / f"{c['id']}_raw.wav"
        final_wav = OUT_DIR / f"{c['id']}.wav"
        
        # Use PowerShell System.Speech.Synthesis
        escaped_text = c['text'].replace("'", "''")
        ps_cmd = (
            f"Add-Type -AssemblyName System.Speech; "
            f"$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$synth.SetOutputToWaveFile('{raw_wav.resolve()}'); "
            f"$synth.Speak('{escaped_text}'); "
            f"$synth.Dispose();"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=True)
        
        # Convert to 24000 Hz mono 16-bit PCM WAV using ffmpeg
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(raw_wav), "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(final_wav), "-y"],
            check=True,
        )
        if raw_wav.exists():
            raw_wav.unlink()
        
        print(f"[OK] Generated {final_wav.name} ({c['label']})")


if __name__ == "__main__":
    generate()
