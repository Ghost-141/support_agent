import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


_BULLET_RE = re.compile(r"^(?P<indent>\s*)[\*\-]\s+")


def _format_telegram_text(text: str) -> str:
    # Normalize common list markers to avoid Markdown rendering issues.
    lines = text.splitlines()
    formatted = []
    for line in lines:
        formatted.append(_BULLET_RE.sub(r"\g<indent>• ", line))
    return "\n".join(formatted)


def send_telegram_message(
    chat_id: str, text: str, parse_mode: str | None = "Markdown"
) -> None:
    """
    Sends a text message via the Telegram Bot API.
    """
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": _format_telegram_text(text),
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    response = requests.post(url, json=payload, timeout=10)
    if response.status_code != 200:
        print("Error sending Telegram message:", response.text)
        response.raise_for_status()
