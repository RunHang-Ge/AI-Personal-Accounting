from decimal import Decimal
from db import get_db_connection


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