"""Small concurrency check (5 parallel requests, uses ~5 real API calls).
  python tools/load_test.py http://127.0.0.1:8000"""
import concurrent.futures
import json
import sys
import time
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
TEXT = "Congratulations! You won $5,000. Pay a $20 fee to claim your prize: bit.ly/claim-now-77"


def one(_):
    t = time.time()
    req = urllib.request.Request(BASE + "/analyze/text", data=json.dumps({"text": TEXT, "language": "English"}).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, time.time() - t
    except Exception as e:
        return str(e)[:60], time.time() - t


with concurrent.futures.ThreadPoolExecutor(5) as pool:
    results = list(pool.map(one, range(5)))
ok = sum(1 for s, _ in results if s == 200)
print(f"{ok}/5 succeeded; slowest {max(t for _, t in results):.1f}s; fastest {min(t for _, t in results):.1f}s")
for s, t in results:
    print(" ", s, f"{t:.1f}s")
sys.exit(0 if ok == 5 else 1)
