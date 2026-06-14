from datetime import date
from decimal import Decimal, InvalidOperation
from db import get_db_connection

from config import ALLOWED_CATEGORIES

def save_transaction(user_id: int, chat_id: int, txn: dict, google_map: str = None):
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
            raw_text,
            google_map
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        google_map,
    ))

    transaction_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    return transaction_id


def execute_add_payload(user_id: int, chat_id: int, payload: dict, raw_text: str, google_map: str | None = None) -> str:
    txn = {
        "txn_date": date.fromisoformat(payload["txn_date"]),
        "category": payload["category"],
        "amount": Decimal(str(payload["amount"])),
        "currency": payload["currency"],
        "merchant": payload.get("merchant"),
        "note": payload.get("note"),
        "raw_text": raw_text
    }

    transaction_id = save_transaction(
        user_id, 
        chat_id, 
        txn,
        google_map)

    return (
        f"已新增账单 #{transaction_id}\n\n"
        f"日期：{txn['txn_date']}\n"
        f"类别：{txn['category']}\n"
        f"金额：{txn['currency']} {txn['amount']}\n"
        f"商户：{txn['merchant'] or '-'}\n"
        f"备注：{txn['note'] or '-'}\n"
        f"Google Map：{google_map or '-'}"
    )