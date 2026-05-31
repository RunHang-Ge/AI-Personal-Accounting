import os
import requests
from fastapi import FastAPI, Request

app = FastAPI()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


@app.get("/")
def health_check():
    return {"status": "ok", "message": "AI Personal Accounting Bot is running"}


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()

    message = data.get("message", {})
    chat = message.get("chat", {})
    text = message.get("text", "")

    chat_id = chat.get("id")

    if chat_id and text:
        reply_text = f"收到：{text}"

        requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": reply_text
            }
        )

    return {"ok": True}