import os
from datetime import date
from decimal import Decimal, InvalidOperation

import psycopg2
import requests
from fastapi import FastAPI, Request


app = FastAPI()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

ALLOWED_CATEGORIES = {
    "餐饮",
    "交通",
    "购物",
    "娱乐",
    "学习",
    "医疗",
    "住房",
    "订阅",
    "其他",
}


def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            telegram_user_id BIGINT NOT NULL,
            telegram_chat_id BIGINT NOT NULL,
            txn_date DATE NOT NULL,
            category TEXT NOT NULL,
            amount NUMERIC(12, 2) NOT NULL,
            currency TEXT NOT NULL,
            merchant TEXT,
            note TEXT,
            raw_text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    conn.commit()
    cur.close()
    conn.close()


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def health_check():
    return {
        "status": "ok",
        "message": "AI Personal Accounting Bot is running"
    }


def send_message(chat_id: int, text: str):
    requests.post(
        f"{TELEGRAM_API_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text
        }
    )


def parse_add_command(text: str):
    content = text.replace("/add", "", 1).strip()
    parts = [p.strip() for p in content.split("|")]

    if len(parts) != 6:
        raise ValueError(
            "格式错误。请使用：\n"
            "/add 日期 | 类别 | 金额 | 币种 | 商户 | 备注\n\n"
            "例如：\n"
            "/add 2026-05-31 | 餐饮 | 28.50 | SGD | 食堂 | 午饭"
        )

    txn_date_text, category, amount_text, currency, merchant, note = parts

    try:
        txn_date = date.fromisoformat(txn_date_text)
    except ValueError:
        raise ValueError("日期格式错误，请使用 YYYY-MM-DD，例如 2026-05-31")

    if category not in ALLOWED_CATEGORIES:
        raise ValueError(
            "类别错误。目前支持：\n" + "、".join(ALLOWED_CATEGORIES)
        )

    try:
        amount = Decimal(amount_text)
    except InvalidOperation:
        raise ValueError("金额格式错误，例如 28.50")

    if amount <= 0:
        raise ValueError("金额必须大于 0")

    currency = currency.upper()

    return {
        "txn_date": txn_date,
        "category": category,
        "amount": amount,
        "currency": currency,
        "merchant": merchant,
        "note": note,
        "raw_text": text,
    }


def parse_query_command(text: str):
    content = text.replace("/query", "", 1).strip()
    params = {}

    if not content:
        return params

    parts = content.split()

    for part in parts:
        if "=" not in part:
            raise ValueError("查询格式错误，请使用 key=value，例如：/query category=餐饮")

        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()

        params[key] = value

    allowed_keys = {"category", "date", "start", "end", "min", "max", "limit"}

    for key in params:
        if key not in allowed_keys:
            raise ValueError(f"不支持的查询条件：{key}")

    if "category" in params and params["category"] not in ALLOWED_CATEGORIES:
        raise ValueError("类别错误。目前支持：" + "、".join(ALLOWED_CATEGORIES))

    if "date" in params:
        date.fromisoformat(params["date"])

    if "start" in params:
        date.fromisoformat(params["start"])

    if "end" in params:
        date.fromisoformat(params["end"])

    if "min" in params:
        Decimal(params["min"])

    if "max" in params:
        Decimal(params["max"])

    if "limit" in params:
        limit = int(params["limit"])
        if limit <= 0 or limit > 50:
            raise ValueError("limit 需要在 1 到 50 之间")

    return params

def query_transactions(user_id: int, params: dict):
    conn = get_db_connection()
    cur = conn.cursor()

    sql = """
        SELECT id, txn_date, category, amount, currency, merchant, note
        FROM transactions
        WHERE telegram_user_id = %s
        AND status = 'active'
    """

    values = [user_id]

    if "category" in params:
        sql += " AND category = %s"
        values.append(params["category"])

    if "date" in params:
        sql += " AND txn_date = %s"
        values.append(params["date"])

    if "start" in params:
        sql += " AND txn_date >= %s"
        values.append(params["start"])

    if "end" in params:
        sql += " AND txn_date <= %s"
        values.append(params["end"])

    if "min" in params:
        sql += " AND amount >= %s"
        values.append(params["min"])

    if "max" in params:
        sql += " AND amount <= %s"
        values.append(params["max"])

    limit = int(params.get("limit", 10))

    sql += " ORDER BY txn_date DESC, id DESC LIMIT %s"
    values.append(limit)

    cur.execute(sql, values)
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows


def format_transactions(rows):
    if not rows:
        return "没有找到符合条件的记录。"

    lines = ["查询结果："]

    for row in rows:
        transaction_id, txn_date, category, amount, currency, merchant, note = row

        lines.append(
            f"#{transaction_id} | {txn_date} | {category} | "
            f"{currency} {amount} | {merchant or '-'} | {note or '-'}"
        )

    return "\n".join(lines)


def save_transaction(user_id: int, chat_id: int, txn: dict):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO transactions (
            telegram_user_id,
            telegram_chat_id,
            txn_date,
            category,
            amount,
            currency,
            merchant,
            note,
            raw_text
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """, (
        user_id,
        chat_id,
        txn["txn_date"],
        txn["category"],
        txn["amount"],
        txn["currency"],
        txn["merchant"],
        txn["note"],
        txn["raw_text"],
    ))

    transaction_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    return transaction_id


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

    if text.startswith("/add"):
        try:
            txn = parse_add_command(text)
            transaction_id = save_transaction(user_id, chat_id, txn)

            reply = (
                f"已记录 #{transaction_id}\n"
                f"日期：{txn['txn_date']}\n"
                f"类别：{txn['category']}\n"
                f"金额：{txn['currency']} {txn['amount']}\n"
                f"商户：{txn['merchant']}\n"
                f"备注：{txn['note']}"
            )

            send_message(chat_id, reply)

        except Exception as e:
            send_message(chat_id, f"记录失败：\n{str(e)}")

    elif text.startswith("/query"):
        try:
            params = parse_query_command(text)
            rows = query_transactions(user_id, params)
            reply = format_transactions(rows)
            send_message(chat_id, reply)

        except Exception as e:
            send_message(chat_id, f"查询失败：\n{str(e)}")

    elif text.startswith("/help"):
        send_message(
            chat_id,
            "记账格式：\n"
            "/add 日期 | 类别 | 金额 | 币种 | 商户 | 备注\n\n"
            "例如：\n"
            "/add 2026-05-31 | 餐饮 | 28.50 | SGD | 食堂 | 午饭\n\n"
            "查询格式：\n"
            "/query\n"
            "/query category=餐饮\n"
            "/query date=2026-05-31\n"
            "/query start=2026-05-01 end=2026-05-31\n"
            "/query min=20 max=100"
        )

    else:
        send_message(
            chat_id,
            "请输入 /help 查看记账格式"
        )

    return {"ok": True}