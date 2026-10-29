"""ScamShield Family - Telegram bot (FAST version).   Run:  python -m app.bot
Elder: forward a message, send a screenshot, or send a voice note.
Family: the elder sends /guardian, the family member sends /join CODE or taps the 1-click invite link.
The bot never saves message content. Only family links and a risk count are stored. /forget deletes everything.

Speed rules used here:
  1. Reply at once ("Checking...") and EDIT that message when the answer is ready.
  2. concurrent_updates(True): one slow check never blocks the next message.
  3. BOT_FAST_MODE=1: our own tools run first, then ONE Muse Spark call (instead of 2 to 3 chained calls).
  4. Screenshots are shrunk, and SAM 3.1 calls run in parallel.
  5. The family gets the TEXT alert immediately; the Muse Image card follows in the background.
"""
import asyncio
import io
import json
import logging
import os
import re
import tempfile
import time

from PIL import Image

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import config, store
from .agent import AgentContext, run_agent, run_agent_fast
from .annotate import draw_regions_png, shrink_image
from .cards import make_comparison_card
from .checks import check_all_links
from .llm import analyze_image
from .sam_refine import refine_with_sam
from .voice import VOICE_LANGUAGES, transcribe_file

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("scamshield")

EMOJI = {"low": "🟢", "medium": "🟠", "high": "🔴"}
SAFE_FALLBACK = "Sorry, something went wrong. To be safe: do not click links, do not pay, and ask someone you trust."
MAX_UPLOAD_BYTES = 32 * 1024 * 1024
HOURLY_CHECK_LIMIT = 20

# Persistent Reply Keyboard with large friendly buttons
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🛡️ Protect Me (Get Code)", "🤝 Join Family (Enter Code)"],
        ["📞 Live Call Guard Code", "🎨 Warning Card"],
        ["🌐 Choose Language", "ℹ️ Status", "🗑️ Delete My Data"],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

LANG_KEYBOARD = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_English"),
            InlineKeyboardButton("🇮🇳 தமிழ் (Tamil)", callback_data="lang_Tamil"),
        ],
        [
            InlineKeyboardButton("🇱🇰 සිංහල (Sinhala)", callback_data="lang_Sinhala"),
            InlineKeyboardButton("🇮🇳 हिन्दी (Hindi)", callback_data="lang_Hindi"),
        ],
    ]
)

WELCOME = (
    "Hi! I am ScamShield 🛡️\n\n"
    "Send me anything that feels strange:\n"
    "• 💬 Forward a message or SMS\n"
    "• 📸 Send a screenshot\n"
    "• 🎙️ Send a voice note\n\n"
    "I will check it with AI and explain it in simple words.\n\n"
    "👇 You can also tap the buttons below without typing commands:"
)


def format_result(r: dict) -> str:
    risk = str(r.get("risk", "medium")).lower()
    lines = [f"{EMOJI.get(risk, '🟠')} Risk: {risk.upper()}", "", str(r.get("verdict", ""))]
    if r.get("reasons"):
        lines += ["", "Why:"] + [f"• {x}" for x in r["reasons"][:4]]
    if r.get("red_flags"):
        lines += ["", "Red flags:"] + [f"• {x}" for x in r["red_flags"][:4]]
    if r.get("next_step"):
        lines += ["", f"👉 What to do: {r['next_step']}"]
    if r.get("actions"):
        lines += ["", "🤖 What I did: " + "; ".join(r["actions"])]
    if r.get("sources"):
        lines += ["", "Sources:"] + [str(source.get("url", "")) for source in r["sources"][:3]]
    return "\n".join(lines)[:3900]


class Stages:
    """Measures where the time goes. Logs stage names and seconds only, never message content."""
    def __init__(self, name: str):
        self.name, self.items, self.t0 = name, [], time.perf_counter()

    async def run(self, label: str, func, *args):
        t = time.perf_counter()
        try:
            return await asyncio.to_thread(func, *args)
        finally:
            self.items.append((label, time.perf_counter() - t))

    def log(self):
        total = time.perf_counter() - self.t0
        log.info("%s timings: %s | total %.1fs", self.name, ", ".join(f"{k} {v:.1f}s" for k, v in self.items), total)


async def safe_edit(msg, text: str, reply_markup=None):
    try:
        await msg.edit_text(text, reply_markup=reply_markup)
    except Exception:
        try:
            await msg.reply_text(text, reply_markup=reply_markup)
        except Exception:
            pass


async def allow_check(update: Update) -> bool:
    if store.consume_check_quota(update.effective_chat.id, HOURLY_CHECK_LIMIT):
        return True
    await update.message.reply_text(
        "You have reached 20 checks in the last hour. Please try again later.",
        reply_markup=MAIN_KEYBOARD,
    )
    return False


async def check_file_size(update: Update, media) -> bool:
    size = getattr(media, "file_size", None)
    if size is not None and size > MAX_UPLOAD_BYTES:
        await update.message.reply_text(
            "Files must be 32 MB or smaller. Please choose a shorter or smaller file.",
            reply_markup=MAIN_KEYBOARD,
        )
        return False
    return True


async def do_join(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str):
    code = code.strip()
    chat_id = update.effective_chat.id
    if not store.allow_join_attempt(chat_id):
        await update.message.reply_text(
            "Too many code attempts. Please wait an hour before trying again.",
            reply_markup=MAIN_KEYBOARD,
        )
        return
    elder = store.accept_invite(chat_id, code)
    if not elder:
        await update.message.reply_text(
            "⚠️ That code is not valid, expired, or you cannot link your own account.\n\n"
            "Please check the 6-digit code or ask your family member to generate a fresh one.",
            reply_markup=MAIN_KEYBOARD,
        )
        return
    user_name = update.effective_user.first_name or ""
    store.upsert_user(chat_id, user_name)
    elder_name = store.get_name(elder)
    await update.message.reply_text(
        f"✅ Success! You now protect {elder_name}.\n\n"
        f"I will instantly warn you if they receive a risky scam message or call.",
        reply_markup=MAIN_KEYBOARD,
    )
    try:
        await context.bot.send_message(
            elder,
            f"✅ {user_name or 'Your family member'} has joined as your guardian!\n\n"
            f"They will receive an instant warning if something risky is detected.",
            reply_markup=MAIN_KEYBOARD,
        )
    except Exception as e:
        log.warning("could not notify elder about joined guardian: %s", e)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    store.upsert_user(update.effective_chat.id, user.first_name or "")

    # Deep-link support: /start join_123456 (1-click join without typing!)
    if context.args and len(context.args) > 0:
        arg = context.args[0].strip()
        if arg.startswith("join_"):
            code = arg.replace("join_", "")
            if len(code) == 6 and code.isdigit():
                await do_join(update, context, code)
                return

    await update.message.reply_text(WELCOME, reply_markup=MAIN_KEYBOARD)


async def language_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        lang = " ".join(context.args).strip().title()
        store.set_language(update.effective_chat.id, lang)
        note = ""
        if lang == "Sinhala":
            note = "\nSinhala voice is not supported yet. Text and screenshots still work."
        elif lang not in VOICE_LANGUAGES:
            note = "\nNote: voice notes may not work well in this language. Text and screenshots are fine."
        await update.message.reply_text(f"✅ Language set to {lang}.{note}", reply_markup=MAIN_KEYBOARD)
        return
    await update.message.reply_text(
        "🌐 Choose your preferred language by tapping a button:",
        reply_markup=LANG_KEYBOARD,
    )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if data.startswith("lang_"):
        lang = data.replace("lang_", "")
        store.set_language(query.from_user.id, lang)
        note = ""
        if lang == "Sinhala":
            note = "\nSinhala voice is not supported yet. Text and screenshots still work."
        elif lang not in VOICE_LANGUAGES:
            note = "\nNote: voice notes may not work well in this language. Text and screenshots are fine."
        await query.edit_message_text(f"✅ Language set to {lang}.{note}")


async def guardian_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = store.create_invite(update.effective_chat.id)
    bot_user = config.TELEGRAM_BOT_USERNAME
    if not bot_user:
        try:
            bot_user = (await context.bot.get_me()).username
        except Exception:
            bot_user = "scamshield_arkesh_bot"
    bot_user = (bot_user or "scamshield_arkesh_bot").lstrip("@")

    join_link = f"https://t.me/{bot_user}?start=join_{code}"
    share_url = f"https://t.me/share/url?url={join_link}&text=Please%20protect%20me%20on%20ScamShield!%20Tap%20the%20link%20to%20join%20instantly:"

    inline_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📲 Send Invite to Family (1-Tap Join)", url=share_url)],
    ])

    await update.message.reply_text(
        f"🛡️ **Your Family Protection Code:** `{code}`\n\n"
        f"The code works for 1 hour.\n\n"
        f"**How your family member can link:**\n"
        f"1️⃣ **Easy 1-Tap:** Tap the button below to send them an invite. When they tap it, they are linked instantly!\n"
        f"2️⃣ **Or Manual:** Tell them to open this bot and simply send the number `{code}` (no slashes needed).",
        reply_markup=inline_kb,
        parse_mode="Markdown",
    )


async def webcode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = store.create_web_code(update.effective_chat.id)
    await update.message.reply_text(
        f"📞 **Your Live Call Guard Code is:** `{code}`\n\n"
        f"Type this 6-digit code on the Call Guard webpage (/guard) to link your speakerphone call to family alerts.\n\n"
        f"The code works for 24 hours.",
        reply_markup=MAIN_KEYBOARD,
        parse_mode="Markdown",
    )


async def join_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Send /join and the 6-digit code, or simply type the 6 digits directly (e.g. 912707).",
            reply_markup=MAIN_KEYBOARD,
        )
        return
    await do_join(update, context, context.args[0])


async def forget_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    store.forget(update.effective_chat.id)
    await update.message.reply_text("Done. I deleted all your data.", reply_markup=MAIN_KEYBOARD)


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛡️ ScamShield Status\n\n"
        f"• Fast Mode: {config.BOT_FAST_MODE}\n"
        f"• Message & Vision: {config.MODEL_NAME}\n"
        f"• Screenshot Marking: sam-3.1\n"
        f"• Voice Transcription: {config.ASR_MODEL}\n"
        f"• Warning Card: {config.IMAGE_MODEL}\n"
        f"• Checks Today (UTC): {store.get_checks_today(update.effective_chat.id)}",
        reply_markup=MAIN_KEYBOARD,
    )


async def card_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scam_type = " ".join(context.args).strip() if context.args else "Suspicious Scam"
    await update.message.chat.send_action("upload_photo")
    await update.message.reply_text(f"🎨 Generating a Real vs Scam comparison card for: **{scam_type}**...", parse_mode="Markdown")
    try:
        card = await asyncio.to_thread(make_comparison_card, scam_type, [])
        if card:
            buf = io.BytesIO(card)
            buf.name = "real_vs_scam.png"
            await update.message.reply_photo(
                photo=buf,
                caption=(
                    f"📚 **Real vs Scam: {scam_type.title()}**\n\n"
                    "Left ✓ shows what a real message looks like.\n"
                    "Right ✗ shows the scam warning signs.\n\n"
                    "_Created with Meta Muse Image. Share this to help your family recognise scams!_"
                ),
                reply_markup=MAIN_KEYBOARD,
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text("Could not generate comparison card. Please try again.", reply_markup=MAIN_KEYBOARD)
    except Exception:
        log.exception("card command failed")
        await update.message.reply_text("Failed to generate comparison card. Please try again.", reply_markup=MAIN_KEYBOARD)


async def _send_comparison_card_later(update: Update, scam_type: str, red_flags: list[str]):
    """Send the elder an educational Real-vs-Scam card after a high-risk result."""
    card = await asyncio.to_thread(make_comparison_card, scam_type, red_flags)
    if not card:
        return
    try:
        buf = io.BytesIO(card)
        buf.name = "real_vs_scam.png"
        await update.message.reply_photo(
            photo=buf,
            caption=(
                "📚 *How to spot this scam next time*\n\n"
                "Left ✓ shows what a real message looks like.\n"
                "Right ✗ shows the tricks used in a scam.\n\n"
                "_Generated by ScamShield with Meta Muse Image_"
            ),
            parse_mode="Markdown",
        )
    except Exception as e:
        log.warning("could not send comparison card: %s", e)


async def send_alerts(bot, elder_id: int, result: dict, ctx: AgentContext, update: Update | None = None):
    guardians = store.get_guardians(elder_id)
    if not guardians or not ctx.alerts:
        return
    alert = ctx.alerts[0]
    name = store.get_name(elder_id)
    text = (
        f"⚠️ {name} just received a possible scam ({alert['scam_type']}, risk {alert['risk']}).\n"
        f"{alert['reason']}\n\n"
        f"👉 Please call {name} before they pay or share any code."
    )
    # 1) The text warning goes out immediately
    for g in guardians:
        try:
            await bot.send_message(g, text)
        except Exception as e:
            log.warning("could not alert %s: %s", g, e)



async def run_case(update: Update, context: ContextTypes.DEFAULT_TYPE, case_text: str, ack, stages: Stages):
    chat_id = update.effective_chat.id
    store.upsert_user(chat_id, update.effective_user.first_name or "")
    lang = store.get_language(chat_id)
    ctx = AgentContext(elder_id=chat_id, has_guardians=bool(store.get_guardians(chat_id)))
    runner = run_agent_fast if config.BOT_FAST_MODE else run_agent
    result = await stages.run("model", runner, case_text, ctx, lang)

    # Safety net: a HIGH risk must always warn the family, even if the model forgot.
    if str(result.get("risk")).lower() == "high" and ctx.has_guardians and not ctx.alerts:
        ctx.alerts.append({"risk": "high", "scam_type": str(result.get("scam_type", "scam")), "reason": str(result.get("verdict", ""))})

    store.log_event(chat_id, str(result.get("risk")), str(result.get("scam_type")))
    await safe_edit(ack, format_result(result), reply_markup=MAIN_KEYBOARD)
    await send_alerts(context.bot, chat_id, result, ctx, update)
    if str(result.get("risk")).lower() == "high":
        scam_type = str(result.get("scam_type") or "scam")
        red_flags = result.get("red_flags") or []
        asyncio.create_task(_send_comparison_card_later(update, scam_type, red_flags))
    stages.log()


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw_text = (update.message.text or "").strip()

    # 1. Easy Button Handlers (no typing needed!)
    if raw_text in ("🛡️ Protect Me (Get Code)", "Protect Me", "Get Code"):
        await guardian_cmd(update, context)
        return
    if raw_text in ("🤝 Join Family (Enter Code)", "Join Family", "Join"):
        await update.message.reply_text(
            "Please send the 6-digit code your family member gave you (e.g. 912707).\n\n"
            "You can simply type the 6 digits directly without any slash commands!",
            reply_markup=MAIN_KEYBOARD,
        )
        return
    if raw_text in ("📞 Live Call Guard Code", "Call Guard Code", "Call Guard"):
        await webcode_cmd(update, context)
        return
    if raw_text in ("🎨 Warning Card", "Warning Card", "Card", "Family Card"):
        await card_cmd(update, context)
        return
    if raw_text in ("🌐 Choose Language", "Language", "Change Language"):
        await language_cmd(update, context)
        return
    if raw_text in ("ℹ️ Status", "Status"):
        await status_cmd(update, context)
        return
    if raw_text in ("🗑️ Delete My Data", "Delete My Data", "Delete Data", "Forget"):
        await forget_cmd(update, context)
        return

    # 2. Direct 6-digit code detection (e.g. "912707" or "join 912707")
    match = re.match(r"^(?:join\s+)?(\d{6})$", raw_text, re.IGNORECASE)
    if match:
        code = match.group(1)
        await do_join(update, context, code)
        return

    # 3. Analyze incoming message for scams
    if not await allow_check(update):
        return

    stages = Stages("text")
    ack = await update.message.reply_text("🔎 Checking... usually a few seconds.", reply_markup=MAIN_KEYBOARD)
    try:
        hints = [l for l in check_all_links(raw_text) if l.get("flags")]  # instant, local
        if hints:
            await safe_edit(ack, "🔎 Checking... ⚠️ This link already looks suspicious: " + hints[0]["flags"][0], reply_markup=MAIN_KEYBOARD)
        await run_case(update, context, f"Message the person received:\n{raw_text}", ack, stages)
    except Exception:
        log.exception("text case failed")
        await safe_edit(ack, SAFE_FALLBACK, reply_markup=MAIN_KEYBOARD)


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await allow_check(update):
        return
    media = update.message.photo[-1] if update.message.photo else update.message.document
    if not media or not await check_file_size(update, media):
        return

    stages = Stages("photo")
    ack = await update.message.reply_text("📷 Looking at your screenshot... usually 10 to 20 seconds.", reply_markup=MAIN_KEYBOARD)
    try:
        file = await media.get_file()
        if not await check_file_size(update, file):
            return
        raw = bytes(await file.download_as_bytearray())
        if len(raw) > MAX_UPLOAD_BYTES:
            await safe_edit(ack, "Files must be 32 MB or smaller. Please choose a smaller image.", reply_markup=MAIN_KEYBOARD)
            return

        data, mime = await asyncio.to_thread(shrink_image, raw)
        lang = store.get_language(update.effective_chat.id)

        vision = await stages.run("vision", analyze_image, data, mime, lang)                              # Muse Spark
        regions = await stages.run("sam", refine_with_sam, data, mime, vision.get("regions", []))        # SAM 3.1 (parallel)
        marked = draw_regions_png(data, regions)
        legend = "\n".join(f"{i}. {r.get('label', '')}: {r.get('reason', '')}" for i, r in enumerate(regions, 1))

        photo_buf = io.BytesIO(marked)
        photo_buf.name = "screenshot_marked.png"
        caption = ("Suspicious parts marked:\n" + legend)[:1000] if legend else "I did not find clear fake parts."
        await update.message.reply_photo(
            photo=photo_buf,
            caption=caption,
            reply_markup=MAIN_KEYBOARD,
        )

        summary = {k: vision.get(k) for k in ("risk", "scam_type", "verdict", "reasons", "red_flags")}
        await run_case(update, context, "A screenshot was checked by vision tools. Findings:\n" + json.dumps(summary, ensure_ascii=False), ack, stages)
    except Exception:
        log.exception("photo case failed")
        await safe_edit(ack, SAFE_FALLBACK, reply_markup=MAIN_KEYBOARD)


async def on_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await allow_check(update):
        return
    media = update.message.voice or update.message.audio
    if not media or not await check_file_size(update, media):
        return

    stages = Stages("voice")
    ack = await update.message.reply_text("🎙️ Listening... usually 10 to 20 seconds.", reply_markup=MAIN_KEYBOARD)
    try:
        file = await media.get_file()
        if not await check_file_size(update, file):
            return
        lang = store.get_language(update.effective_chat.id)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "note.ogg")
            await file.download_to_drive(path)
            if os.path.getsize(path) > MAX_UPLOAD_BYTES:
                await safe_edit(ack, "Audio files must be 32 MB or smaller. Please choose a shorter recording.", reply_markup=MAIN_KEYBOARD)
                return
            transcript = await stages.run("transcribe", transcribe_file, path, lang)   # Muse Voice Transcribe
        if not transcript:
            await safe_edit(ack, "I could not hear any words. Please try again.", reply_markup=MAIN_KEYBOARD)
            return
        await safe_edit(ack, f"🎙️ I heard: {transcript[:600]}\n\n🔎 Checking...", reply_markup=MAIN_KEYBOARD)
        await run_case(update, context, f"Voice note the person received (transcribed):\n{transcript}", ack, stages)
    except (ValueError, RuntimeError) as e:
        await safe_edit(ack, str(e), reply_markup=MAIN_KEYBOARD)
    except Exception:
        log.exception("voice case failed")
        await safe_edit(ack, SAFE_FALLBACK, reply_markup=MAIN_KEYBOARD)


def main():
    if not config.TELEGRAM_BOT_TOKEN:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in your .env file (create a bot with @BotFather).")
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("language", language_cmd))
    app.add_handler(CommandHandler("guardian", guardian_cmd))
    app.add_handler(CommandHandler("webcode", webcode_cmd))
    app.add_handler(CommandHandler("card", card_cmd))
    app.add_handler(CommandHandler("join", join_cmd))
    app.add_handler(CommandHandler("forget", forget_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE | filters.Document.MimeType("image/png") | filters.Document.MimeType("image/jpeg") | filters.Document.MimeType("image/webp"), on_photo))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info("ScamShield bot is running (fast mode: %s). Press Ctrl+C to stop.", config.BOT_FAST_MODE)
    app.run_polling()


if __name__ == "__main__":
    main()
