# Manual Browser & Judge Verification Checklist

> [!IMPORTANT]
> **To comply strictly with hackathon evaluation rules, no automated browser tools (Playwright/Selenium/headless browsers) are run on this machine.**
> This checklist is designed for human judges and developers to test all interactive visual capabilities manually in Chrome, Safari, Edge, or Firefox.

---

## Prerequisites
1. Ensure dependencies are installed: `pip install -r requirements.txt`
2. Start the local server:
   ```bash
   uvicorn app.main:app --port 8000
   ```
3. Open `http://localhost:8000` (or `http://127.0.0.1:8000`) in your browser. (Note: browser microphone APIs require `localhost` or HTTPS).

---

## 1. Main Dashboard (`http://localhost:8000/`)

- [ ] **Initial Page Load & Meta Theme:**
  - Verify Meta gradient hero banner displays with title *"Check before you click, pay or share"*.
  - Verify active model strip displays: `Muse Spark 1.3`, `SAM 3.1`, `Muse Voice Transcribe 1.0`, `Muse Image 1.0`.
  - Click **"Toggle dark mode"** in top bar. Verify theme toggles smoothly with high-contrast borders.
  - Click **"Bigger text"** in top bar. Verify root font size scales to 20px+ for elder readability.
  - Click **"Show a saved example"** in the Judge Tour banner. Verify real pipeline execution with timings and SAM segmentation displays instantly.

- [ ] **Tab 1: Message (Text Analysis):**
  - Click the **"Bank SMS"** sample button.
  - Click **"Check this"**.
  - Verify risk badge turns **HIGH** (red).
  - Verify explanation reveals reason, red flags, and next step (*"Do not tap the link"*).
  - Expand **"Show raw agent trace"** drawer; verify redacted tools executed (`check_links`).

- [ ] **Tab 2: Screenshot (Vision + SAM 3.1):**
  - Switch to the **"Screenshot"** tab.
  - Drop a screenshot (e.g. from `data/demo_screenshot.png` or `static/demo/demo_screenshot.png`).
  - Click **"Check screenshot"**.
  - Verify SAM 3.1 bounding boxes highlight deceptive elements (e.g., suspicious bank logo, urgent text banner).
  - Hover over the interactive slider or legend items to toggle box highlighting.

- [ ] **Tab 3 & 4: Voice Note & Call Recording:**
  - Record or upload an audio note. Verify speech is transcribed via Muse Voice Transcribe and displayed with verbatim transcript.

---

## 2. Live Call Guard (`http://localhost:8000/guard`)

- [ ] **Navigation & Consent:**
  - Click **"🔴 Live Call Guard"** in the top bar.
  - Verify page loads with high-contrast status banner: *"Ready: Press 'Guard this call' to start."*
  - Try clicking **"Guard this call"** without ticking consent checkbox. Verify error: *"Please tick the box to confirm you are allowed to listen to this call."*
  - Tick consent checkbox.

- [ ] **Audio Streaming & Speakerphone Simulation:**
  - **Option A (Audio File Test - No mic needed):**
    - Click **"Test with an audio file"**.
    - Select `data/synthetic_calls/call_01_synthetic_bank_otp.wav`.
    - Watch real-time streaming: pulsing green dot *"Listening"*.
    - Observe the transcript grow live turn-by-turn.
    - Within seconds, verify banner turns **HIGH (red)** with pulse animation and audio chime: *"HANG UP IMMEDIATELY"*.
    - Verify threat chip: `Code` and `Secrecy`.
  - **Option B (Safe Control Test):**
    - Click **"Test with an audio file"** and select `data/synthetic_calls/call_04_synthetic_clinic_appointment.wav`.
    - Watch real-time streaming: banner remains **GREEN ("All clear so far")**; no alarm sounds.
  - **Option C (Live Microphone Test):**
    - Click **"Guard this call"** and allow microphone access.
    - Put your phone on speakerphone or speak into the microphone: *"Give me your bank OTP code right now."*
    - Verify instant high-risk banner trigger.

- [ ] **Family Web Code Pairing:**
  - Send `/webcode` to the Telegram bot to generate a 6-digit code.
  - Type the 6-digit code into the **"Family code (optional)"** field before pressing start.
  - Verify status banner displays: *"Your family will be warned if this becomes dangerous."*
  - When a scam turn occurs, verify that the linked guardian receives an immediate Telegram alert with categorized threats (and no raw transcript leaks).
