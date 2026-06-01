from datetime import date, timedelta

from db import get_db_connection


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
        SELECT currency, COUNT(*), SUM(amount)
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
        SELECT {group_column}, currency, COUNT(*), SUM(amount)
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

    lines = [
        f"账单汇总：{start_date} 至 {end_date}",
        "",
        "总支出："
    ]

    for currency, transaction_count, total_amount in total_rows:
        lines.append(f"{currency} {total_amount}｜{transaction_count} 笔")

    lines.append("")

    if group_by == "category":
        lines.append("按类别汇总：")
    else:
        lines.append("按日期汇总：")

    for group_key, currency, transaction_count, total_amount in group_rows:
        lines.append(f"{group_key}｜{currency} {total_amount}｜{transaction_count} 笔")

    return "\n".join(lines)


def handle_summary_command(user_id: int, text: str):
    params = parse_summary_command(text)
    summary = summarize_transactions(user_id, params)
    return format_summary(summary)


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