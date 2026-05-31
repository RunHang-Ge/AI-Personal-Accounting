from datetime import date
from decimal import Decimal, InvalidOperation

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