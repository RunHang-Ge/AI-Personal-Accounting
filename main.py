from fastapi import FastAPI, Request

from db import init_db
from telegram_api import send_message
from add_command import handle_add_command
from query_command import handle_query_command
from summary_command import handle_summary_command
from update_command import handle_update_command
from datetime import date


app = FastAPI()


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "message": "AI Personal Accounting Bot is running"
    }


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()

    message = data.get("message", {})
    chat = message.get("chat", {})
    user = message.get("from", {})

    chat_id = chat.get("id")
    user_id = user.get("id")
    text = message.get("text", "")

    if not chat_id or not text:
        return {"ok": True}

    try:
        if text.startswith("/add"):
            reply = handle_add_command(user_id, chat_id, text)

        elif text.startswith("/query"):
            reply = handle_query_command(user_id, text)

        elif text.startswith("/summary"):
            reply = handle_summary_command(user_id, text)

        elif text.startswith("/update"):
            reply = handle_update_command(user_id, text)

        elif text.startswith("/help"):
            reply = get_help_text()

        else:
            reply = "请输入 /help 查看支持的指令。"

    except Exception as e:
        reply = f"操作失败：\n{str(e)}"

    send_message(chat_id, reply)

    return {"ok": True}


def get_help_text():
    return (
        "支持指令：\n\n"
        "1. 新增账单：\n"
        "/add\n"
        "日期\n"
        "类别\n"
        "币种 金额\n"
        "商户\n"
        "备注\n\n"
        "例如：\n"
        "/add\n"
        "2026-05-31\n"
        "餐饮\n"
        "SGD 28.50\n"
        "食堂\n"
        "午饭\n\n"
        "2. 查询账单：\n"
        "/query\n"
        "/query category=餐饮\n"
        "/query date=2026-05-31\n"
        "/query min=20 max=100\n\n"
        "3. 汇总账单：\n"
        "/summary\n"
        "/summary group=date\n"
        "/summary month=2026-05\n\n"
        "4. 修改账单：\n"
        "/update 记录ID 字段=新值\n"
        "例如：/update 3 category=交通 amount=32.50"
    )