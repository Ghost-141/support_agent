from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.background import BackgroundTasks
from dotenv import load_dotenv
import os

from agent import run_agent
from api.dependency import get_db_pool
from api.services.telegram import send_telegram_message
from psycopg_pool import AsyncConnectionPool

load_dotenv()

telegram_router = APIRouter()

MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "1000"))
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")


@telegram_router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    pool: AsyncConnectionPool = Depends(get_db_pool),
):
    if TELEGRAM_WEBHOOK_SECRET:
        header_value = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if header_value != TELEGRAM_WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="invalid secret token")

    data = await request.json()
    background_tasks.add_task(process_telegram_update, data, pool)
    return {"status": "received"}


async def process_telegram_update(data: dict, pool: AsyncConnectionPool):
    message = (
        data.get("message")
        or data.get("edited_message")
        or data.get("channel_post")
        or data.get("edited_channel_post")
    )
    if not message:
        return

    text = message.get("text")
    if not text:
        return

    chat = message.get("chat", {})
    chat_id = chat.get("id")
    if chat_id is None:
        return

    user_id = f"tg:{chat_id}"

    if len(text) > MAX_MESSAGE_LENGTH:
        send_telegram_message(
            chat_id=chat_id,
            text="Your message is too long. Please try again with a shorter message.",
        )
        return

    response = await run_agent(text, user_id, pool, channel="telegram")
    send_telegram_message(chat_id=chat_id, text=response)
