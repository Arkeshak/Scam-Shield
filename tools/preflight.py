"""ScamShield preflight: one command that checks the whole project.

  python tools/preflight.py            # offline checks only (free)
  python tools/preflight.py --live     # also makes a few REAL Meta API calls (uses a little credit)

It prints PASS / FAIL / SKIP for each check and never prints secret values.
Exit code is 1 if anything FAILED.
"""
import argparse
import importlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

RESULTS = []


def record(name, status, detail=""):
    RESULTS.append((name, status, detail))
    icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "SKIP": "[SKIP]"}[status]
    print(f"{icon} {name}" + (f"  -> {detail}" if detail else ""), flush=True)


def run(cmd, timeout=300):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
        return p.returncode, (p.stdout + p.stderr).strip()
    except Exception as e:
        return 1, str(e)


def load_env():
    env = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


# ---------- checks ----------
def check_python():
    ok = sys.version_info >= (3, 10)
    record("Python version >= 3.10", "PASS" if ok else "FAIL", sys.version.split()[0])


def check_files():
    required = [
        "app/__init__.py", "app/config.py", "app/checks.py", "app/llm.py", "app/sam_refine.py", "app/annotate.py",
        "app/agent.py", "app/voice.py", "app/call.py", "app/cards.py", "app/store.py", "app/bot.py", "app/main.py",
        "app/guard.py", "app/guard_rules.py", "app/notify.py", "static/index.html", "static/guard.html",
        "evaluate.py", "tests_offline.py", "tests_api_offline.py", "tests_guard_offline.py", "requirements.txt",
        ".env.example", ".gitignore", "README.md", "data/test_set.csv",
    ]
    missing = [f for f in required if not (ROOT / f).exists()]
    record("Required files exist", "FAIL" if missing else "PASS", ("missing: " + ", ".join(missing)) if missing else f"{len(required)} files")
    nice = ["LICENSE", "docs/DEMO_SCRIPT.md", "docs/SUBMISSION.md", "data/heldout_set.csv", "data/eval_results.json"]
    gone = [f for f in nice if not (ROOT / f).exists()]
    record("Submission extras exist", "FAIL" if gone else "PASS", ("missing: " + ", ".join(gone)) if gone else "")


def check_imports():
    bad = []
    for mod in ["config", "checks", "llm", "sam_refine", "annotate", "agent", "voice", "call", "cards", "store", "guard_rules", "notify", "guard", "bot", "main"]:
        try:
            importlib.import_module(f"app.{mod}")
        except Exception as e:
            bad.append(f"{mod}: {type(e).__name__}: {str(e)[:80]}")
    record("All app modules import", "FAIL" if bad else "PASS", "; ".join(bad))


def check_pip():
    code, out = run([sys.executable, "-m", "pip", "check"])
    record("pip check (no broken packages)", "PASS" if code == 0 else "FAIL", out.splitlines()[-1] if out else "")


def check_tests():
    for t in ["tests_offline.py", "tests_api_offline.py", "tests_guard_offline.py", "tests_speed_offline.py"]:
        code, out = run([sys.executable, t])
        record(f"{t}", "PASS" if code == 0 else "FAIL", out.splitlines()[-1] if out else "")


SKIP_DIRS = {".git", "venv", ".venv", "node_modules", "__pycache__", "tmp", "outputs", ".claude", ".codex", ".cursor", ".history", "checkpoints", ".idea", ".vscode"}
PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|bearer|password)\s*[:=]\s*['\"]?([A-Za-z0-9_\-:\.]{24,})"),
    re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b"),  # Telegram bot token shape
]
PLACEHOLDER = re.compile(r"(?i)(paste|your|example|placeholder|xxxx|changeme|<)")


def check_secrets():
    hits = {}
    for path in ROOT.rglob("*"):
        if path.is_dir() or any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if path.name == ".env" or path.suffix in {".png", ".jpg", ".jpeg", ".zip", ".db", ".pdf", ".webp", ".wav", ".ogg"} or path.stat().st_size > 1_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for line in text.splitlines():
            for pat in PATTERNS:
                m = pat.search(line)
                if m and not PLACEHOLDER.search(line):
                    hits[str(path.relative_to(ROOT))] = hits.get(str(path.relative_to(ROOT)), 0) + 1
    record("No secret-looking values in project files", "FAIL" if hits else "PASS", ", ".join(f"{k} ({v})" for k, v in list(hits.items())[:8]))


def check_gitignore():
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8", errors="ignore") if (ROOT / ".gitignore").exists() else ""
    need = [".env", "*.db", "venv"]
    miss = [n for n in need if n not in gi]
    record(".gitignore covers .env, *.db, venv", "FAIL" if miss else "PASS", "missing: " + ", ".join(miss) if miss else "")
    if (ROOT / ".git").exists():
        code, out = run(["git", "ls-files"])
        tracked = [l for l in out.splitlines() if l == ".env" or l.endswith(".db") or l.startswith("venv/")]
        record("Git does not track .env / .db / venv", "FAIL" if tracked else "PASS", ", ".join(tracked[:5]))
    else:
        record("Git does not track .env / .db / venv", "SKIP", "not a git repo")


def check_env(env):
    key = bool(env.get("MODEL_API_KEY")) and "paste" not in env.get("MODEL_API_KEY", "").lower()
    record(".env has MODEL_API_KEY", "PASS" if key else "FAIL", "set" if key else "missing or placeholder")
    tok = bool(env.get("TELEGRAM_BOT_TOKEN")) and "paste" not in env.get("TELEGRAM_BOT_TOKEN", "").lower()
    record(".env has TELEGRAM_BOT_TOKEN", "PASS" if tok else "SKIP", "set" if tok else "not set (bot cannot run)")
    record(".env has TELEGRAM_BOT_USERNAME", "PASS" if env.get("TELEGRAM_BOT_USERNAME") and "your_bot" not in env.get("TELEGRAM_BOT_USERNAME", "") else "SKIP", "")


def check_ffmpeg():
    record("ffmpeg installed (voice notes)", "PASS" if shutil.which("ffmpeg") else "FAIL", "" if shutil.which("ffmpeg") else "install ffmpeg")


def check_static():
    for name in ["index.html", "guard.html"]:
        path = ROOT / "static" / name
        if not path.exists():
            record(f"static/{name} exists", "FAIL")
            continue
        html = path.read_text(encoding="utf-8", errors="ignore")
        external = re.findall(r"""(?:src|href)\s*=\s*["'](https?://[^"']+)""", html)
        external = [u for u in external if "github.com" not in u and "t.me" not in u]
        record(f"{name}: no external scripts, fonts or images", "FAIL" if external else "PASS", ", ".join(external[:4]))
        record(f"{name}: escapes model output (esc helper present)", "PASS" if re.search(r"const esc\s*=|function esc\(", html) else "FAIL")
        if shutil.which("node"):
            scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
            tmp = ROOT / "tmp"
            tmp.mkdir(exist_ok=True)
            ok = True
            for i, sc in enumerate(scripts):
                f = tmp / f"{name}.{i}.js"
                f.write_text(sc, encoding="utf-8")
                code, out = run(["node", "--check", str(f)])
                ok = ok and code == 0
            record(f"{name}: JavaScript syntax (node --check)", "PASS" if ok else "FAIL")
        else:
            record(f"{name}: JavaScript syntax (node --check)", "SKIP", "node not installed")


def check_data():
    import csv
    path = ROOT / "data" / "test_set.csv"
    if path.exists():
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        labels = {r.get("label") for r in rows}
        ok = len(rows) >= 100 and labels <= {"scam", "safe"}
        record("Development set has >= 100 rows, labels scam/safe", "PASS" if ok else "FAIL", f"{len(rows)} rows")
    held = ROOT / "data" / "heldout_set.csv"
    if held.exists():
        rows = list(csv.DictReader(open(held, encoding="utf-8")))
        record("Held-out set has >= 40 rows", "PASS" if len(rows) >= 40 else "FAIL", f"{len(rows)} rows")
    else:
        record("Held-out set has >= 40 rows", "FAIL", "data/heldout_set.csv missing")
    for name in ["eval_results.json", "eval_heldout.json"]:
        p = ROOT / "data" / name
        if p.exists():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                record(f"data/{name} valid", "PASS" if "accuracy" in d and d.get("n") else "FAIL", f"n={d.get('n')} acc={d.get('accuracy')}")
            except Exception as e:
                record(f"data/{name} valid", "FAIL", str(e)[:80])
        else:
            record(f"data/{name} valid", "FAIL" if name == "eval_heldout.json" else "SKIP", "missing")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def get(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", errors="ignore")


def start_server():
    port = free_port()
    env = dict(os.environ)
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)], cwd=ROOT, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        try:
            if get(f"http://127.0.0.1:{port}/health", 2)[0] == 200:
                return proc, port
        except Exception:
            time.sleep(0.5)
    try:
        proc.kill()
    except Exception:
        pass
    return None, port


def check_server(live):
    proc, port = start_server()
    if not proc:
        record("Web server starts and /health answers", "FAIL", "server did not start")
        return None, None
    base = f"http://127.0.0.1:{port}"
    record("Web server starts and /health answers", "PASS", base)
    try:
        for path, needle in [("/", "ScamShield"), ("/guard", "Live Call Guard"), ("/api/config", "models"), ("/api/metrics", "")]:
            try:
                status, body = get(base + path)
                record(f"GET {path}", "PASS" if status == 200 and needle in body else "FAIL", f"HTTP {status}")
            except Exception as e:
                record(f"GET {path}", "FAIL", str(e)[:80])
        # negative tests (no API calls are made for these)
        import urllib.error
        req = urllib.request.Request(base + "/analyze/text", data=json.dumps({"text": "  "}).encode(), headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=10)
            record("Empty text is rejected (HTTP 400)", "FAIL", "accepted")
        except urllib.error.HTTPError as e:
            record("Empty text is rejected (HTTP 400)", "PASS" if e.code in (400, 422) else "FAIL", f"HTTP {e.code}")
        if live:
            check_live(base)
    finally:
        try:
            proc.kill()
        except Exception:
            pass
    return proc, port



def check_live(base):
    env = load_env()
    if not env.get("MODEL_API_KEY"):
        record("LIVE checks", "SKIP", "no MODEL_API_KEY")
        return
    import urllib.error
    # 1) text agent
    fake = "URGENT: Your bank account is locked. Verify now at http://secure-b4nk-login.xyz/verify or it will close in 2 hours."
    try:
        t = time.time()
        req = urllib.request.Request(base + "/analyze/text", data=json.dumps({"text": fake, "language": "English"}).encode(), headers={"Content-Type": "application/json"})
        d = json.loads(urllib.request.urlopen(req, timeout=120).read())
        ok = d.get("risk") in ("medium", "high") and d.get("verdict") and isinstance(d.get("reasons"), list)
        record("LIVE: text agent flags a fake bank SMS", "PASS" if ok else "FAIL", f"risk={d.get('risk')} in {time.time() - t:.1f}s actions={d.get('actions')}")
    except Exception as e:
        record("LIVE: text agent flags a fake bank SMS", "FAIL", str(e)[:120])
    safe = "Hi, your dentist appointment is tomorrow at 3 PM. Reply YES to confirm."
    try:
        req = urllib.request.Request(base + "/analyze/text", data=json.dumps({"text": safe, "language": "English"}).encode(), headers={"Content-Type": "application/json"})
        d = json.loads(urllib.request.urlopen(req, timeout=120).read())
        record("LIVE: text agent keeps a normal message low risk", "PASS" if d.get("risk") == "low" else "FAIL", f"risk={d.get('risk')}")
    except Exception as e:
        record("LIVE: text agent keeps a normal message low risk", "FAIL", str(e)[:120])
    # 2) screenshot through Spark + SAM 3.1
    demo = next((p for p in [ROOT / "data" / "demo_screenshot.png", ROOT / "static" / "demo" / "demo_screenshot.png"] if p.exists()), None)
    if demo:
        try:
            import uuid
            boundary = uuid.uuid4().hex
            body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\nEnglish\r\n"
                    f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"demo.png\"\r\nContent-Type: image/png\r\n\r\n").encode() \
                   + demo.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
            req = urllib.request.Request(base + "/analyze/image", data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
            d = json.loads(urllib.request.urlopen(req, timeout=180).read())
            regions = d.get("regions", [])
            sam = sum(1 for r in regions if r.get("source") == "sam-3.1")
            record("LIVE: screenshot analysed (Muse Spark)", "PASS" if d.get("verdict") else "FAIL", f"{len(regions)} region(s)")
            record("LIVE: SAM 3.1 refined at least one box", "PASS" if sam else "FAIL", f"{sam} SAM box(es)")
            record("LIVE: timings returned", "PASS" if d.get("timings") else "FAIL", "")
        except Exception as e:
            record("LIVE: screenshot + SAM 3.1", "FAIL", str(e)[:120])
    else:
        record("LIVE: screenshot + SAM 3.1", "SKIP", "no demo screenshot in data/ or static/demo/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="make a few real API calls")
    args = ap.parse_args()
    env = load_env()
    for k, v in env.items():
        os.environ.setdefault(k, v)
    print(f"ScamShield preflight in {ROOT}\n")
    for fn in (check_python, check_files, check_imports, check_pip, check_tests, check_secrets, check_gitignore, check_ffmpeg, check_static, check_data):
        try:
            fn()
        except Exception as e:
            record(fn.__name__, "FAIL", f"{type(e).__name__}: {e}"[:150])
    check_env(env)
    try:
        check_server(args.live)
    except Exception as e:
        record("check_server", "FAIL", f"{type(e).__name__}: {e}"[:150])
    fails = [r for r in RESULTS if r[1] == "FAIL"]
    skips = [r for r in RESULTS if r[1] == "SKIP"]
    print(f"\nSUMMARY: {len(RESULTS) - len(fails) - len(skips)} passed, {len(fails)} failed, {len(skips)} skipped")
    if fails:
        print("FAILED:")
        for n, _, d in fails:
            print(f"  - {n}: {d}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
