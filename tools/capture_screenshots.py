import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import shutil

EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(EDGE_PATH):
    EDGE_PATH = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

OUT_DIR = os.path.abspath("docs/screenshots")
PUBLIC_OUT_DIR = r"C:\Users\ASUS\Desktop\scamshield-public\docs\screenshots"
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(PUBLIC_OUT_DIR, exist_ok=True)

def wait_server(url, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False

def take_screenshot(url, out_path, width, height, delay_ms=1000):
    tmp_user_data = os.path.join(tempfile.gettempdir(), f"edge_shot_{int(time.time()*1000)}")
    os.makedirs(tmp_user_data, exist_ok=True)
    cmd = [
        EDGE_PATH,
        "--headless",
        "--no-sandbox",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--user-data-dir={tmp_user_data}",
        f"--window-size={width},{height}",
        f"--virtual-time-budget={delay_ms}",
        f"--screenshot={out_path}",
        url
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=15)
    finally:
        shutil.rmtree(tmp_user_data, ignore_errors=True)

def main():
    print("Starting FastAPI app with uvicorn on port 8000...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    try:
        if not wait_server("http://127.0.0.1:8000/"):
            print("Server failed to respond on http://127.0.0.1:8000/")
            return 1
        print("Server is up! Capturing updated screenshots...")

        tasks = [
            ("home_1280.png", "http://127.0.0.1:8000/", 1280, 920, 1000),
            ("dark_mode.png", "http://127.0.0.1:8000/?theme=dark", 1280, 920, 1000),
            ("tablet_768.png", "http://127.0.0.1:8000/", 768, 1024, 1000),
            ("mobile_375.png", "http://127.0.0.1:8000/?mobile=1", 375, 812, 1000),
            ("screenshot_result_compare.png", "http://127.0.0.1:8000/?example=1", 1280, 1100, 2500),
        ]

        for filename, url, w, h, delay in tasks:
            out_file = os.path.join(OUT_DIR, filename)
            take_screenshot(url, out_file, w, h, delay)
            if os.path.exists(out_file):
                print(f"Captured {filename} ({w}x{h}) - size: {os.path.getsize(out_file)} bytes")
                shutil.copy2(out_file, os.path.join(PUBLIC_OUT_DIR, filename))
            else:
                print(f"Failed to capture {filename}")

        # Also copy comparison_card.png if present
        comp_card = os.path.join(OUT_DIR, "comparison_card.png")
        if os.path.exists(comp_card):
            shutil.copy2(comp_card, os.path.join(PUBLIC_OUT_DIR, "comparison_card.png"))
            print(f"Synced comparison_card.png to public repo")

    finally:
        print("Terminating server...")
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
    print("Done!")
    return 0

if __name__ == "__main__":
    sys.exit(main())

