# Submission details

- **Project title:** ScamShield Family
- **One-line pitch:** A tool-using AI scam bodyguard that checks suspicious
  messages, marks screenshot evidence, transcribes voice, and can warn a linked
  family member before they act.
- **Track:** Indie developer
- **Theme:** Build for Your World; Push the Frontier

## Description (150 words)

ScamShield Family helps people pause before paying, clicking, or sharing a
private code. A family member can check a suspicious message, screenshot, voice
note, recorded call, or use the headline feature: **Live Call Guard**.
With Live Call Guard, an elder puts an incoming suspicious call on speakerphone;
live audio streams over full-duplex WebSocket to Meta’s Muse Voice Transcribe
realtime endpoint. The moment pressure tactics appear (asking for OTPs, money,
gift cards, or secrecy), an unmistakable high-contrast alarm tells them to HANG UP,
while an instant Telegram alert notifies their family.
Muse Spark provides structured analysis and tool-grounded explanations. SAM 3.1
outlines fake interface elements on screenshots. Muse Image generates a Real-vs-Scam
comparison card that teaches the elder to spot the pattern. The system stores zero audio or message content,
protecting elder privacy.

## Meta models

| Model | Role | Code |
|---|---|---|
| Muse Spark (`muse-spark-1.3`) | Structured scam analysis, tool-using agent, screenshot/call reasoning, background call guard evaluation | `app/llm.py`, `app/agent.py`, `app/guard.py` |
| SAM 3.1 (`sam-3.1`) | Segment screenshot objects and refine suspicious boxes | `app/sam_refine.py` |
| Muse Voice Transcribe (`muse-voice-transcribe-1.0`) | Voice-note transcription and recorded call diarization | `app/voice.py`, `app/call.py` |
| Muse Voice Transcribe Realtime (`wss://api.meta.ai/v1/asr/realtime`) | Full-duplex realtime speech recognition for Live Call Guard speakerphone monitoring | `app/guard.py` |
| Muse Image (`muse-image-1.0`) | Real-vs-Scam educational comparison card — sent to the elder after a high-risk result to teach pattern recognition; also available via web UI and `POST /api/comparison_card` | `app/cards.py` |


## Links to fill in

- Public repository: **[add URL]**
- Three-minute demo video: **[add URL]**
- Hackathon submission: **[add URL]**
- Project owner / full name: **[add name]**

## Pre-submission checklist

- [ ] Repository is public and the intended branch is pushed.
- [ ] Demo-video link opens in a private/incognito window.
- [ ] README claims match the final measured results.
- [ ] No `.env`, API keys, Telegram tokens, databases, recordings, or personal data
  are committed.
- [ ] Project owner name and all required team/participant names are added.
- [ ] Submission is complete before Nov 4 afternoon Sri Lanka time and before
  the official Nov 4, 9:00 PM ET deadline.
- [ ] Hackathon model credits have been claimed; spending and remaining balance
  have been checked.
- [ ] Live Meta API, ffmpeg, and Telegram tests are described honestly, including
  any that still need a second consenting account.
