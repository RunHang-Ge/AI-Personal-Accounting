import os
from datetime import date, timedelta
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

def get_current_month_range():
    today = date.today()
    start_date = today.replace(day=1)

    if start_date.month == 12:
        next_month = date(start_date.year + 1, 1, 1)
    else:
        next_month = date(start_date.year, start_date.month + 1, 1)

    end_date = next_month - timedelta(days=1)
    return start_date, end_date


def get_month_range(month_text: str):
    try:
        year, month = month_text.split("-")
        year = int(year)
        month = int(month)
        start_date = date(year, month, 1)

        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)

        end_date = next_month - timedelta(days=1)
        return start_date, end_date

    except Exception:
        raise ValueError("month 格式错误，请使用 YYYY-MM，例如：month=2026-05")


def parse_summary_command(text: str):
    content = text.replace("/summary", "", 1).strip()
    params = {}

    if content:
        parts = content.split()

        for part in parts:
            if "=" not in part:
                raise ValueError("汇总格式错误，请使用 key=value，例如：/summary month=2026-05 group=category")

            key, value = part.split("=", 1)
            params[key.strip()] = value.strip()

    allowed_keys = {"month", "start", "end", "group"}

    for key in params:
        if key not in allowed_keys:
            raise ValueError(f"不支持的汇总条件：{key}")

    group_by = params.get("group", "category")

    if group_by not in {"category", "date"}:
        raise ValueError("group 只支持 category 或 date")

    if "month" in params and ("start" in params or "end" in params):
        raise ValueError("month 不能和 start/end 同时使用")

    if "month" in params:
        start_date, end_date = get_month_range(params["month"])

    elif "start" in params or "end" in params:
        if "start" not in params or "end" not in params:
            raise ValueError("使用 start/end 时必须同时提供，例如：start=2026-05-01 end=2026-05-31")

        start_date = date.fromisoformat(params["start"])
        end_date = date.fromisoformat(params["end"])

        if start_date > end_date:
            raise ValueError("start 不能晚于 end")

    else:
        start_date, end_date = get_current_month_range()

    return {
        "start_date": start_date,
        "end_date": end_date,
        "group_by": group_by,
    }

def summarize_transactions(user_id: int, params: dict):
    start_date = params["start_date"]
    end_date = params["end_date"]
    group_by = params["group_by"]

    if group_by == "category":
        group_column = "category"
        order_by = "SUM(amount) DESC"
    else:
        group_column = "txn_date"
        order_by = "txn_date ASC"

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            currency,
            COUNT(*) AS transaction_count,
            SUM(amount) AS total_amount
        FROM transactions
        WHERE telegram_user_id = %s
          AND status = 'active'
          AND txn_date >= %s
          AND txn_date <= %s
        GROUP BY currency
        ORDER BY currency;
    """, (user_id, start_date, end_date))

    total_rows = cur.fetchall()

    sql = f"""
        SELECT
            {group_column} AS group_key,
            currency,
            COUNT(*) AS transaction_count,
            SUM(amount) AS total_amount
        FROM transactions
        WHERE telegram_user_id = %s
          AND status = 'active'
          AND txn_date >= %s
          AND txn_date <= %s
        GROUP BY {group_column}, currency
        ORDER BY {order_by};
    """

    cur.execute(sql, (user_id, start_date, end_date))
    group_rows = cur.fetchall()

    cur.close()
    conn.close()

    return {
        "start_date": start_date,
        "end_date": end_date,
        "group_by": group_by,
        "total_rows": total_rows,
        "group_rows": group_rows,
    }

def format_summary(summary: dict):
    start_date = summary["start_date"]
    end_date = summary["end_date"]
    group_by = summary["group_by"]
    total_rows = summary["total_rows"]
    group_rows = summary["group_rows"]

    if not total_rows:
        return f"没有找到 {start_date} 至 {end_date} 的账单记录。"

    lines = []
    lines.append(f"账单汇总：{start_date} 至 {end_date}")
    lines.append("")

    lines.append("总支出：")
    for currency, transaction_count, total_amount in total_rows:
        lines.append(f"{currency} {total_amount}｜{transaction_count} 笔")

    lines.append("")

    if group_by == "category":
        lines.append("按类别汇总：")
    else:
        lines.append("按日期汇总：")

    for group_key, currency, transaction_count, total_amount in group_rows:
        lines.append(
            f"{group_key}｜{currency} {total_amount}｜{transaction_count} 笔"
        )

    return "\n".join(lines)




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

    elif text.startswith("/summary"):
        try:
            params = parse_summary_command(text)
            summary = summarize_transactions(user_id, params)
            reply = format_summary(summary)
            send_message(chat_id, reply)

        except Exception as e:
            send_message(chat_id, f"汇总失败：\n{str(e)}")

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
            "/query min=20 max=100\n"
            "汇总格式：\n"
            "/summary\n"
            "/summary group=category\n"
            "/summary group=date\n"
            "/summary month=2026-05\n"
            "/summary month=2026-05 group=date\n"
            "/summary start=2026-05-01 end=2026-05-31 group=category"
        )

    else:
        send_message(
            chat_id,
            "请输入 /help 查看记账格式"
        )

    return {"ok": True}