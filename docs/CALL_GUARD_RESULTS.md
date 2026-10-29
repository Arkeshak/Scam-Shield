# Live Call Guard: Benchmark and Realtime Latency Evaluation

This document records the exact, unrounded latency and detection metrics of **Live Call Guard** running over WebSocket against Meta's Muse Voice Transcribe realtime endpoint (`wss://api.meta.ai/v1/asr/realtime`).

> [!NOTE]
> All audio clips used in this evaluation were generated synthetically using Windows `System.Speech.Synthesis` and resampled with `ffmpeg` (24,000 Hz, 16-bit mono PCM). They are labeled as synthetic test calls.

---

## 1. Test Architecture & Methodology

- **Transport:** Full-duplex WebSocket (`/ws/guard`) connecting client to backend proxy, which maintains a persistent WebSocket session with Meta's Realtime ASR endpoint in `ENDPOINTING` mode.
- **Audio Framing:** 80 ms frames at 24 kHz (1,920 samples = 3,840 bytes) with drift-free pacing.
- **Dual-Engine Evaluation:**
  1. Microsecond local regex rule-matcher (`app/guard_rules.py`) executed synchronously on every completed turn.
  2. Asynchronous background evaluation cycles using Meta Muse Spark (`app/llm.py`) without audio interruption.
  3. Single-event Telegram guardian alert dispatched on transition to `high` risk.

---

## 2. Empirical Benchmark Results (Live Run)

| Call ID | Type | Ground Truth | Audio Duration | First Turn Time | First High Banner Time | Final Risk Level | Guardian Alert Sent | Detection Result |
|---|---|---|---|---|---|---|---|---|
| `call_01_synthetic_bank_otp.wav` | Bank OTP & Secrecy Pressure | **Scam** | 17.7s | 14.81s | **14.81s** | **HIGH** | Yes | ✅ True Positive |
| `call_02_synthetic_police_warrant.wav` | Police Arrest Threat & Gift Card | **Scam** | 16.9s | 16.88s | **16.88s** | **HIGH** | Yes | ✅ True Positive |
| `call_03_synthetic_remote_support.wav` | Urgent Virus & AnyDesk Install | **Scam** | 16.1s | 16.22s | **16.22s** | **HIGH** | Yes | ✅ True Positive |
| `call_04_synthetic_clinic_appointment.wav` | Clinic Dental Checkup Reminder | **Safe** | 16.1s | 11.55s | *Never* | **LOW** | No | ✅ True Negative |
| `call_05_synthetic_delivery_notice.wav` | Courier Doorstep Delivery Drop | **Safe** | 12.9s | 13.16s | *Never* | **LOW** | No | ✅ True Negative |
| `call_06_synthetic_family_chat.wav` | Family Member Sunday Dinner Chat | **Safe** | 15.0s | 10.02s | *Never* | **LOW** | No | ✅ True Negative |

---

## 3. Summary Performance Metrics

- **Total Calls Evaluated:** 6 (3 scam, 3 safe controls)
- **Scam Detection Recall:** **100%** (3/3 flagged high risk)
- **Safe Control False Positive Rate:** **0%** (0/3 false alarms; all 3 remained low risk)
- **Time to Banner:**
  - Bank OTP scam: **14.81s** from call start (triggered instantly on completion of turn 1)
  - Police warrant scam: **16.88s** from call start (triggered instantly on completion of turn 1)
  - Remote support scam: **16.22s** from call start (triggered instantly on completion of turn 1)
- **Guardian Notification:** Dispatched exactly once per scam call, containing categorized threat descriptors without leaking private elder transcripts.
- **Failures / Errors:** 0
