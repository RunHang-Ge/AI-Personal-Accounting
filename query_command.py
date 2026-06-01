from db import get_db_connection


def execute_query_payload(user_id: int, payload: dict) -> str:
    where_clauses = ["telegram_user_id = %s"]
    params = [user_id]

    if payload.get("category"):
        where_clauses.append("category = %s")
        params.append(payload["category"])

    if payload.get("date_from"):
        where_clauses.append("txn_date >= %s")
        params.append(payload["date_from"])

    if payload.get("date_to"):
        where_clauses.append("txn_date <= %s")
        params.append(payload["date_to"])

    if payload.get("min_amount") is not None:
        where_clauses.append("amount >= %s")
        params.append(payload["min_amount"])

    if payload.get("max_amount") is not None:
        where_clauses.append("amount <= %s")
        params.append(payload["max_amount"])

    if payload.get("currency"):
        where_clauses.append("currency = %s")
        params.append(payload["currency"])

    if payload.get("merchant"):
        where_clauses.append("merchant ILIKE %s")
        params.append(f"%{payload['merchant']}%")

    if payload.get("keyword"):
        where_clauses.append("(merchant ILIKE %s OR note ILIKE %s OR raw_text ILIKE %s)")
        keyword = f"%{payload['keyword']}%"
        params.extend([keyword, keyword, keyword])

    limit = payload.get("limit", 20)
    limit = min(max(int(limit), 1), 50)

    sql = f"""
        SELECT id, txn_date, category, amount, currency, merchant, note
        FROM transactions
        WHERE {" AND ".join(where_clauses)}
        ORDER BY txn_date DESC, id DESC
        LIMIT %s
    """

    params.append(limit)

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return "没有找到符合条件的账单。"

    lines = [f"查询结果：共 {len(rows)} 条\n"]

    for row in rows:
        transaction_id, txn_date, category, amount, currency, merchant, note = row

        lines.append(
            f"#{transaction_id} | {txn_date} | {category} | "
            f"{currency} {amount} | {merchant or '-'} | {note or '-'}"
        )

    return "\n".join(lines)
