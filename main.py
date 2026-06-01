from fastapi import FastAPI, Request

from db import init_db
from telegram_api import send_message

from ai_parser import (
    parse_add_with_ai,
    parse_query_with_ai,
    parse_summary_with_ai,
    parse_update_with_ai,
    revise_payload_with_ai
)

from pending_action import (
    set_pending_action,
    cancel_pending_action,
    execute_pending_action,
    format_preview,
    has_pending_action,
    get_pending_action,
    update_pending_action
)

app = FastAPI()

def split_command_and_content(text: str):
    text = text.strip()

    if not text.startswith("/"): #如果开头没有/，command = None
        return None, text

    lines = text.splitlines()
    first_line = lines[0].strip()

    parts = first_line.split(maxsplit=1) #这里限制指令和后续内容之间，必须要有一个空格，不然无法识别
    command = parts[0]

    first_line_content = parts[1].strip() if len(parts) > 1 else ""
    rest_content = "\n".join(lines[1:]).strip()

    content = "\n".join(
        part for part in [first_line_content, rest_content]
        if part
    ).strip()

    return command, content #最终返回 【查询命令，每一行content用/n连接】



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
    text = message.get("text", "").strip()

    if not chat_id or not text:
        return {"ok": True}

    try:
        if text == "确认":
            reply = execute_pending_action(user_id, chat_id)

        elif text == "取消":
            reply = cancel_pending_action(chat_id)

        elif has_pending_action(chat_id):
            pending_action = get_pending_action(chat_id)

            action_type = pending_action["type"]
            current_payload = pending_action["payload"]

            new_payload = revise_payload_with_ai(
                action_type=action_type,
                current_payload=current_payload,
                revision_text=text
            )

            update_pending_action(
                chat_id=chat_id,
                new_payload=new_payload,
                revision_text=text
            )
            reply = format_preview(action_type, new_payload)

        else:
            command, content = split_command_and_content(text)

            if command == "/add":
                if not content:
                    reply = "请输入要新增的账单内容，例如：\n/add 今天中午在食堂吃饭花了 28.5 新币"
                else:
                    payload = parse_add_with_ai(content)

                    set_pending_action(
                        chat_id=chat_id,
                        action_type="add",
                        payload=payload,
                        raw_text=text
                    )

                    reply = format_preview("add", payload)

            elif command == "/query":
                if not content:
                    reply = "请输入查询条件，例如：\n/query 查一下这个月餐饮超过 20 新币的记录"
                else:
                    payload = parse_query_with_ai(content)

                    set_pending_action(
                        chat_id=chat_id,
                        action_type="query",
                        payload=payload,
                        raw_text=text
                    )

                    reply = format_preview("query", payload)

            elif command == "/summary":
                if not content:
                    reply = "请输入汇总条件，例如：\n/summary 汇总这个月每个类别花了多少钱"
                else:
                    payload = parse_summary_with_ai(content)

                    set_pending_action(
                        chat_id=chat_id,
                        action_type="summary",
                        payload=payload,
                        raw_text=text
                    )

                    reply = format_preview("summary", payload)

            elif command == "/update":
                if not content:
                    reply = "请输入修改内容，例如：\n/update 把第 3 条记录的类别改成交通，备注改成打车"
                else:
                    payload = parse_update_with_ai(content)

                    set_pending_action(
                        chat_id=chat_id,
                        action_type="update",
                        payload=payload,
                        raw_text=text
                    )

                    reply = format_preview("update", payload)

            elif command in ["/start", "/help"]:
                reply = get_help_text()

            else:
                reply = "无法识别命令。请输入 /help 查看用法。"

    except Exception as e:
        reply = f"操作失败：\n{str(e)}"

    send_message(chat_id, reply)

    return {"ok": True}


def get_help_text():
    return (
        "支持指令：\n\n"
        "1. 新增账单：\n"
        "/add + 你想执行的动作\n\n"
        "2. 查询账单：\n"
        "/query + 你想执行的动作\n\n"
        "3. 汇总账单：\n"
        "/summary + 你想执行的动作\n\n"
        "4. 修改账单：\n"
        "/update + 你想执行的动作（目前只支持按ID更新）"
    )

