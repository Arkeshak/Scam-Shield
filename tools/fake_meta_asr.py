"""A FAKE Meta realtime transcription server for offline testing (no internet, no credits).
  python tools/fake_meta_asr.py 9911
Then run the app with:  GUARD_ASR_WS=ws://127.0.0.1:9911  MODEL_API_KEY=test  uvicorn app.main:app
After about 1 second of audio it 'hears' a scam sentence. Use it to test the pipeline, never as proof of accuracy."""
import asyncio
import json
import sys

import websockets

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9911
SENTENCES = ["Hello, this is the bank security team.", "Do not tell anyone. Read me the code you just received, right now."]


async def handler(ws):
    json.loads(await ws.recv())                       # handshake
    await ws.send(json.dumps({"sessionId": "fake"}))
    total, said = 0, 0
    async for msg in ws:
        if isinstance(msg, bytes):
            total += len(msg)
            seconds = total / 48000
            while said < len(SENTENCES) and seconds >= 1.0 + said * 1.5:
                await ws.send(json.dumps({"type": "transcript", "transcript": SENTENCES[said][:12], "final": False, "audioProcessedMs": int(seconds * 1000)}))
                await ws.send(json.dumps({"type": "speechComplete", "turnId": said + 1, "transcript": SENTENCES[said], "audioProcessedMs": int(seconds * 1000)}))
                said += 1
        elif json.loads(msg).get("type") == "endStream":
            await ws.close(1000)
            return


async def main():
    async with websockets.serve(handler, "127.0.0.1", PORT):
        print(f"fake Meta ASR on ws://127.0.0.1:{PORT}")
        await asyncio.Future()


asyncio.run(main())
