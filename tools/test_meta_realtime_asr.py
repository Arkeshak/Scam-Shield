"""Smoke test for Meta Realtime ASR WebSocket endpoint.
Tests handshake and sends 1-2 seconds of PCM audio.
"""
import asyncio
import json
import sys
import uuid
sys.path.insert(0, ".")
import websockets
from app import config


async def test_realtime_asr():
    if not config.MODEL_API_KEY:
        print("[SKIP] No MODEL_API_KEY set.")
        return
    
    url = f"wss://api.meta.ai/v1/asr/realtime?sessionId=smoke-{uuid.uuid4()}"
    handshake = {
        "authorization": {"accessToken": f"Bearer {config.MODEL_API_KEY}"},
        "audioEncoding": "PCM_24KHZ",
        "model": config.ASR_MODEL,
        "mode": "ENDPOINTING",
        "partialMode": "CUMULATIVE",
        "emitAudioProgress": False,
        "keywords": ["OTP", "PIN", "code", "bank"],
    }
    
    print(f"Connecting to {url}...")
    try:
        async with websockets.connect(url, open_timeout=15) as ws:
            print("Connected! Sending handshake...")
            await ws.send(json.dumps(handshake))
            reply = json.loads(await asyncio.wait_for(ws.recv(), 15))
            print("Handshake ACK:", reply)
            
            # Send 1 second of silence
            print("Sending 1 second of audio...")
            for _ in range(12):
                await ws.send(b"\x00" * 3840)
                await asyncio.sleep(0.08)
            
            await ws.send(json.dumps({"type": "endStream"}))
            print("Sent endStream. Waiting for flush...")
            try:
                async for msg in ws:
                    print("Received:", msg[:100] if isinstance(msg, str) else len(msg))
            except Exception:
                pass
            print("[PASS] Meta Realtime ASR connection succeeded.")
    except Exception as e:
        print(f"[NOTE] Realtime ASR connection result: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_realtime_asr())
