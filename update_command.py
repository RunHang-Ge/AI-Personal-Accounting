from datetime import date
from decimal import Decimal, InvalidOperation

from config import ALLOWED_CATEGORIES
from db import get_db_connection


def format_transaction_detail(row):
    transaction_id, txn_date, category, amount, currency, merchant, note = row

    return (
        f"已更新 #{transaction_id}\n"
        f"日期：{txn_date}\n"
        f"类别：{category}\n"
        f"金额：{currency} {amount}\n"
        f"商户：{merchant or '-'}\n"
        f"备注：{note or '-'}"
    )


def parse_update_command(text: str):
    content = text.replace("/update", "", 1).strip()

    if not content:
        raise ValueError(
            "修改格式错误。请使用：\n"
            "/update 记录ID 字段=新值\n\n"
            "例如：\n"
            "/update 3 category=交通 amount=32.50"
        )

    parts = content.split()

    if len(parts) < 2:
        raise ValueError("请至少提供记录ID和一个修改字段。")

    try:
        transaction_id = int(parts[0])
    except ValueError:
        raise ValueError("记录ID必须是数字，例如：/update 3 category=交通")

    allowed_fields = {
        "date",
        "category",
        "amount",
        "currency",
        "merchant",
        "note",
    }

    updates = {}

    for part in parts[1:]:
        if "=" not in part:
            raise ValueError("字段格式错误，请使用 key=value，例如 category=交通")

        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()

        if key not in allowed_fields:
            raise ValueError("不支持修改字段。支持字段：date、category、amount、currency、merchant、note")

        if key == "date":
            updates["txn_date"] = date.fromisoformat(value)

        elif key == "category":
            if value not in ALLOWED_CATEGORIES:
                raise ValueError("类别错误。目前支持：" + "、".join(ALLOWED_CATEGORIES))
            updates["category"] = value

        elif key == "amount":
            try:
                amount = Decimal(value)
            except InvalidOperation:
                raise ValueError("金额格式错误，例如 28.50")

            if amount <= 0:
                raise ValueError("金额必须大于 0")

            updates["amount"] = amount

        elif key == "currency":
            updates["currency"] = value.upper()

        elif key == "merchant":
            updates["merchant"] = None if value in {"-", "null", "None"} else value

        elif key == "note":
            updates["note"] = None if value in {"-", "null", "None"} else value

    return transaction_id, updates


def update_transaction(user_id: int, transaction_id: int, updates: dict):
    conn = get_db_connection()
    cur = conn.cursor()

    set_clause = ", ".join([f"{field} = %s" for field in updates.keys()])
    values = list(updates.values())
    values.extend([transaction_id, user_id])

    sql = f"""
        UPDATE transactions
        SET {set_clause}
        WHERE id = %s
          AND telegram_user_id = %s
          AND status = 'active'
        RETURNING id, txn_date, category, amount, currency, merchant, note;
    """

    cur.execute(sql, values)
    row = cur.fetchone()

    conn.commit()
    cur.close()
    conn.close()

    return row


def handle_update_command(user_id: int, text: str):
    transaction_id, updates = parse_update_command(text)
    row = update_transaction(user_id, transaction_id, updates)

    if not row:
        return "修改失败：没有找到这条记录，或这条记录不属于你。"

    return format_transaction_detail(row)

def execute_update_payload(user_id: int, payload: dict) -> str:
    transaction_id = payload.get("transaction_id")

    if not transaction_id:
        return "修改失败：没有识别到要修改的账单 ID。请明确输入例如：/update 把第 3 条记录的类别改成交通。"

    fields = payload.get("fields", {})

    allowed_fields = {
        "txn_date": "txn_date",
        "category": "category",
        "amount": "amount",
        "currency": "currency",
        "merchant": "merchant",
        "note": "note"
    }

    update_clauses = []
    params = []

    for key, column in allowed_fields.items():
        value = fields.get(key)

        if value is None:
            continue

        update_clauses.append(f"{column} = %s")

        if key == "amount":
            params.append(Decimal(str(value)))
        else:
            params.append(value)

    if not update_clauses:
        return "修改失败：没有识别到需要修改的字段。"

    sql = f"""
        UPDATE transactions
        SET {", ".join(update_clauses)}
        WHERE id = %s AND telegram_user_id = %s
        RETURNING id, txn_date, category, amount, currency, merchant, note
    """

    params.extend([transaction_id, user_id])

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            conn.commit()
    finally:
        conn.close()

    if not row:
        return f"修改失败：没有找到属于你的 #{transaction_id} 账单。"

    transaction_id, txn_date, category, amount, currency, merchant, note = row

    return (
        f"已修改账单 #{transaction_id}\n\n"
        f"日期：{txn_date}\n"
        f"类别：{category}\n"
        f"金额：{currency} {amount}\n"
        f"商户：{merchant or '-'}\n"
        f"备注：{note or '-'}"
    )