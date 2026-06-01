from db import get_db_connection


def execute_summary_payload(user_id: int, payload: dict) -> str:
    where_clauses = ["telegram_user_id = %s"]
    params = [user_id]

    if payload.get("date_from"):
        where_clauses.append("txn_date >= %s")
        params.append(payload["date_from"])

    if payload.get("date_to"):
        where_clauses.append("txn_date <= %s")
        params.append(payload["date_to"])

    if payload.get("category"):
        where_clauses.append("category = %s")
        params.append(payload["category"])

    if payload.get("currency"):
        where_clauses.append("currency = %s")
        params.append(payload["currency"])

    group_by = payload.get("group_by", "category")

    if group_by == "date":
        group_sql = "txn_date"
        group_title = "日期"
    else:
        group_sql = "category"
        group_title = "类别"

    sql = f"""
        SELECT {group_sql} AS group_key, currency, COUNT(*) AS count, SUM(amount) AS total
        FROM transactions
        WHERE {" AND ".join(where_clauses)}
        GROUP BY {group_sql}, currency
        ORDER BY {group_sql}
    """

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return "没有找到可汇总的账单。"

    lines = [f"汇总结果：按{group_title}汇总\n"]

    for row in rows:
        group_key, currency, count, total = row
        lines.append(
            f"{group_key} | {currency} {total} | {count} 条"
        )

    return "\n".join(lines)