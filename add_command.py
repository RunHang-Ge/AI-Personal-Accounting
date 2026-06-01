from datetime import date
from decimal import Decimal, InvalidOperation
from db import get_db_connection

from config import ALLOWED_CATEGORIES


def parse_money_line(money_text: str):
    parts = money_text.strip().split()

    if len(parts) != 2:
        raise ValueError("金额行格式错误，请使用：SGD 28.50")

    first, second = parts

    try:
        amount = Decimal(first)
        currency = second.upper()
    except InvalidOperation:
        try:
            currency = first.upper()
            amount = Decimal(second)
        except InvalidOperation:
            raise ValueError("金额格式错误，请使用：SGD 28.50")

    if amount <= 0:
        raise ValueError("金额必须大于 0")

    return currency, amount


def parse_add_command(text: str):
    content = text.replace("/add", "", 1).strip()

    lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip()
    ]

    if len(lines) != 5:
        raise ValueError(
            "记账格式错误。请使用：\n\n"
            "/add\n"
            "2026-05-31\n"
            "餐饮\n"
            "SGD 28.50\n"
            "食堂\n"
            "午饭"
        )

    txn_date_text = lines[0]
    category = lines[1]
    money_text = lines[2]
    merchant = lines[3]
    note = lines[4]

    try:
        txn_date = date.fromisoformat(txn_date_text)
    except ValueError:
        raise ValueError("日期格式错误，请使用 YYYY-MM-DD，例如 2026-05-31")

    if category not in ALLOWED_CATEGORIES:
        raise ValueError("类别错误。目前支持：" + "、".join(ALLOWED_CATEGORIES))

    currency, amount = parse_money_line(money_text)

    return {
        "txn_date": txn_date,
        "category": category,
        "amount": amount,
        "currency": currency,
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

def execute_add_payload(user_id: int, chat_id: int, payload: dict, raw_text: str) -> str:
    txn = {
        "txn_date": date.fromisoformat(payload["txn_date"]),
        "category": payload["category"],
        "amount": Decimal(str(payload["amount"])),
        "currency": payload["currency"],
        "merchant": payload.get("merchant"),
        "note": payload.get("note"),
        "raw_text": raw_text
    }

    transaction_id = save_transaction(user_id, chat_id, txn)

    return (
        f"已新增账单 #{transaction_id}\n\n"
        f"日期：{txn['txn_date']}\n"
        f"类别：{txn['category']}\n"
        f"金额：{txn['currency']} {txn['amount']}\n"
        f"商户：{txn['merchant'] or '-'}\n"
        f"备注：{txn['note'] or '-'}"
    )