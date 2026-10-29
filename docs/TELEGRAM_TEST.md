# Telegram manual test checklist

A real two-account test needs the owner’s approval and two consenting Telegram
accounts. Never paste the bot token into this checklist or a public issue.

## Setup

1. In local `.env`, set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_BOT_USERNAME`.
2. Restart `python -m app.bot`. The username is the public bot handle without
   the leading `@`.
3. Use a disposable test bot and synthetic examples. Confirm you can message
   both test accounts and that neither contains real family messages.

## Basic behavior

- [ ] Account A: `/start` returns the welcome text.
- [ ] Account A: submit
  `URGENT: This fictional account closes today. Send a test payment to claim your sample parcel.`
  and verify it returns a risk explanation and action steps.
- [ ] Account A: send `data/demo_screenshot.png`; verify a marked screenshot and
  legend or an honest “no clear fake parts found” response.
- [ ] Account A: send an authorized synthetic English voice note; verify
  transcript and analysis. If Sinhala is selected, verify the clear unsupported
  language message.
- [ ] Account A: `/language Tamil` updates the language.
- [ ] Account A: `/status` lists configured model IDs and the UTC daily check
  count without message content.
- [ ] Account A: `/guardian` returns a temporary code. Account B: `/join CODE`
  confirms the link on both accounts.
- [ ] Account A: submit the fictional high-risk payment request; verify one
  delivered guardian warning. Confirm a text-only warning arrives if card
  generation is deliberately unavailable in a separate test environment.
- [ ] Account A: submit a normal appointment reminder; verify no guardian alert.
- [ ] Account B: `/forget` removes its relationship; verify Account A no longer
  alerts that guardian. Account A: `/forget` removes its own data.
- [ ] In a disposable account, send 20 checks, then a 21st inside an hour;
  verify the rate-limit explanation. Verify an oversized file is rejected
  before analysis.

Record pass/fail, approximate time, bot build/commit, and redacted screenshots.
Do not include tokens, user names, chat IDs, message content, or personal data in
evidence. The checklist is not a claim that a real Telegram test has passed.
