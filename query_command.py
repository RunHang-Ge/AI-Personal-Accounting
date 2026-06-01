from datetime import date
from decimal import Decimal

from config import ALLOWED_CATEGORIES
from db import get_db_connection


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
        params[key.strip()] = value.strip()

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


def handle_query_command(user_id: int, text: str):
    params = parse_query_command(text)
    rows = query_transactions(user_id, params)
    return format_transactions(rows)

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
