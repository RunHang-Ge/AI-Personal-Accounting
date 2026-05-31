from datetime import date
from decimal import Decimal, InvalidOperation

from config import ALLOWED_CATEGORIES
from db import get_db_connection


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
        raise ValueError("类别错误。目前支持：" + "、".join(ALLOWED_CATEGORIES))

    try:
        amount = Decimal(amount_text)
    except InvalidOperation:
        raise ValueError("金额格式错误，例如 28.50")

    if amount <= 0:
        raise ValueError("金额必须大于 0")

    return {
        "txn_date": txn_date,
        "category": category,
        "amount": amount,
        "currency": currency.upper(),
        "merchant": merchant,
        "note": note,
        "raw_text": text,
    }


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


def handle_add_command(user_id: int, chat_id: int, text: str):
    txn = parse_add_command(text)
    transaction_id = save_transaction(user_id, chat_id, txn)

    return (
        f"已记录 #{transaction_id}\n"
        f"日期：{txn['txn_date']}\n"
        f"类别：{txn['category']}\n"
        f"金额：{txn['currency']} {txn['amount']}\n"
        f"商户：{txn['merchant']}\n"
        f"备注：{txn['note']}"
    )