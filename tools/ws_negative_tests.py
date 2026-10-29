"""Negative tests for Live Call Guard's WebSocket (no browser needed).
  python tools/ws_negative_tests.py ws://127.0.0.1:8000/ws/guard
The server must be running. The 'busy' test opens max-sessions real sessions for a few seconds
(about $0 of audio). Default max-sessions=2 matches GUARD_MAX_SESSIONS_PER_IP default (2), so
all sessions originate from the same IP and the per-IP limit fires on session max+1."""
import argparse
import asyncio
import json
import sys

import websockets

ap = argparse.ArgumentParser()
ap.add_argument("url", nargs="?", default="ws://127.0.0.1:8000/ws/guard")
ap.add_argument("--max-sessions", type=int, default=2)
args = ap.parse_args()
results = []


def record(name, ok, detail=""):
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""))


async def first_reply(first_frame, timeout=15):
    async with websockets.connect(args.url, open_timeout=15) as ws:
        await ws.send(first_frame)
        try:
            return json.loads(await asyncio.wait_for(ws.recv(), timeout))
        except websockets.ConnectionClosed as e:
            return {"type": "closed", "code": e.rcvd.code if e.rcvd else None}
        except Exception as e:
            return {"type": "exception", "detail": str(e)[:60]}


async def main():
    r = await first_reply(json.dumps({"type": "start", "consent": False}))
    record("no consent is refused", r.get("type") == "error", r.get("message", "")[:70])

    r = await first_reply("this is not json")
    record("garbage first frame does not crash the server", r.get("type") in ("closed", "error"), str(r)[:70])

    r = await first_reply(json.dumps({"type": "hello"}))
    record("wrong first message type is refused", r.get("type") in ("error", "closed"), str(r)[:70])

    held = []
    try:
        for i in range(args.max_sessions):
            ws = await websockets.connect(args.url, open_timeout=15)
            await ws.send(json.dumps({"type": "start", "consent": True, "language": "English"}))
            m = json.loads(await asyncio.wait_for(ws.recv(), 20))
            held.append(ws)
            if m.get("type") != "ready":
                record(f"session {i + 1} can start", False, str(m)[:80])
                return
        r = await first_reply(json.dumps({"type": "start", "consent": True, "language": "English"}))
        record(f"session {args.max_sessions + 1} gets a friendly 'busy' message", r.get("type") == "error" and "busy" in r.get("message", "").lower(), str(r)[:80])
    finally:
        for ws in held:
            try:
                await ws.send(json.dumps({"type": "stop"}))
                await ws.close()
            except Exception:
                pass


asyncio.run(main())
print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
