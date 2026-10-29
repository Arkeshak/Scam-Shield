"""Measure how fast Live Call Guard reacts to a recorded call (acts like the browser, at real-time speed).
  python tools/guard_latency.py fake_call.wav --url ws://127.0.0.1:8000/ws/guard --language English [--code 123456] [--expect high]
Needs ffmpeg. Prints seconds from the START of the audio to the first turn, the first 'medium' and the first 'high' banner."""
import argparse
import asyncio
import json
import subprocess
import sys
import time

import websockets

ap = argparse.ArgumentParser()
ap.add_argument("audio")
ap.add_argument("--url", default="ws://127.0.0.1:8000/ws/guard")
ap.add_argument("--language", default="English")
ap.add_argument("--code", default="")
ap.add_argument("--expect", choices=["low", "medium", "high"], default=None)
ap.add_argument("--tail", type=float, default=4.0, help="seconds of silence sent after the audio so the last turn can finish")
args = ap.parse_args()

pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", args.audio, "-ac", "1", "-ar", "24000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
FRAME = 3840  # 80 ms at 24 kHz, 16-bit mono
duration = len(pcm) / 48000
silence = b"\x00" * FRAME * int(args.tail / 0.08)
events = {}


async def main():
    async with websockets.connect(args.url, open_timeout=20, max_size=2**22) as ws:
        await ws.send(json.dumps({"type": "start", "consent": True, "language": args.language, "webCode": args.code}))
        ready = json.loads(await ws.recv())
        if ready.get("type") != "ready":
            print("Could not start:", ready)
            sys.exit(2)
        t0 = time.monotonic()
        texts = []

        async def reader():
            async for raw in ws:
                m = json.loads(raw)
                now = round(time.monotonic() - t0, 2)
                if m["type"] == "turn":
                    events.setdefault("first_turn", now)
                    texts.append((now, m["text"]))
                elif m["type"] == "risk":
                    events.setdefault("level_" + m["level"], now)
                    events["final_level"] = m["level"]
                    events["alerted"] = m.get("alerted")
                elif m["type"] in ("ended", "error"):
                    if m["type"] == "error":
                        events["error"] = m.get("message")
                    return

        task = asyncio.create_task(reader())
        data = pcm + silence
        for i in range(0, len(data), FRAME):
            await ws.send(data[i:i + FRAME])
            await asyncio.sleep(max(0, t0 + (i // FRAME + 1) * 0.08 - time.monotonic()))   # real-time pacing, no drift
        await ws.send(json.dumps({"type": "stop"}))
        try:
            await asyncio.wait_for(task, 20)
        except asyncio.TimeoutError:
            pass
        print(f"audio length: {duration:.1f}s")
        for k in ("first_turn", "level_medium", "level_high"):
            print(f"{k}: {events.get(k, 'never')}" + ("s" if k in events else ""))
        print("final level:", events.get("final_level", "low"), "| alert triggered:", events.get("alerted"), "| error:", events.get("error"))
        for t, x in texts[:8]:
            print(f"  [{t:>5}s] {x[:100]}")


asyncio.run(main())
final = events.get("final_level", "low")
sys.exit(1 if args.expect and final != args.expect else 0)
