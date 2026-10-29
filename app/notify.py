"""Send a Telegram message to a family guardian WITHOUT needing the bot process to be running.
Uses the plain Telegram HTTP API with the same bot token."""
import requests

from . import config, store


def telegram_send(chat_id: int, text: str) -> bool:
    if not config.TELEGRAM_BOT_TOKEN:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=15,
        )
        return r.ok
    except Exception:
        return False   # never log the URL: it contains the token


def notify_guardians(elder_id: int, text: str) -> int:
    """Returns how many guardians were alerted."""
    sent = 0
    for guardian in store.get_guardians(elder_id):
        if telegram_send(guardian, text):
            sent += 1
    return sent
