import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

ADD_SCHEMA = {
        "type": "object",
        "properties": {
            "txn_date": {"type": "string"},
            "category": {
                "type": "string",
                "enum": ["餐饮", "交通", "购物", "娱乐", "住房", "医疗", "学习", "旅行", "其他"]
            },
            "amount": {"type": "number"},
            "currency": {"type": "string"},
            "merchant": {"type": ["string", "null"]},
            "note": {"type": ["string", "null"]}
        },
        "required": ["txn_date", "category", "amount", "currency", "merchant", "note"],
        "additionalProperties": False
    }

QUERY_SCHEMA = {
        "type": "object",
        "properties": {
            "category": {
                "type": ["string", "null"],
                "enum": ["餐饮", "交通", "购物", "娱乐", "住房", "医疗", "学习", "旅行", "其他", None]
            },
            "date_from": {"type": ["string", "null"]},
            "date_to": {"type": ["string", "null"]},
            "min_amount": {"type": ["number", "null"]},
            "max_amount": {"type": ["number", "null"]},
            "currency": {"type": ["string", "null"]},
            "merchant": {"type": ["string", "null"]},
            "keyword": {"type": ["string", "null"]},
            "limit": {"type": "integer"}
        },
        "required": [
            "category",
            "date_from",
            "date_to",
            "min_amount",
            "max_amount",
            "currency",
            "merchant",
            "keyword",
            "limit"
        ],
        "additionalProperties": False
    }

SUMMARY_SCHEMA = {
        "type": "object",
        "properties": {
            "group_by": {
                "type": "string",
                "enum": ["category", "date"]
            },
            "date_from": {"type": ["string", "null"]},
            "date_to": {"type": ["string", "null"]},
            "category": {
                "type": ["string", "null"],
                "enum": ["餐饮", "交通", "购物", "娱乐", "住房", "医疗", "学习", "旅行", "其他", None]
            },
            "currency": {"type": ["string", "null"]}
        },
        "required": ["group_by", "date_from", "date_to", "category", "currency"],
        "additionalProperties": False
    }

UPDATE_SCHEMA = {
        "type": "object",
        "properties": {
            "transaction_id": {"type": ["integer", "null"]},
            "fields": {
                "type": "object",
                "properties": {
                    "txn_date": {"type": ["string", "null"]},
                    "category": {
                        "type": ["string", "null"],
                        "enum": ["餐饮", "交通", "购物", "娱乐", "住房", "医疗", "学习", "旅行", "其他", None]
                    },
                    "amount": {"type": ["number", "null"]},
                    "currency": {"type": ["string", "null"]},
                    "merchant": {"type": ["string", "null"]},
                    "note": {"type": ["string", "null"]}
                },
                "required": ["txn_date", "category", "amount", "currency", "merchant", "note"],
                "additionalProperties": False
            }
        },
        "required": ["transaction_id", "fields"],
        "additionalProperties": False
    }


def today_sg() -> str:
    return datetime.now(ZoneInfo("Asia/Singapore")).date().isoformat()

# 当前版本AI是不包括上下文，每次的解析仅限于当前文本
def call_ai_parser(content: str, schema_name: str, schema: dict, instruction: str) -> dict:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")

    today = today_sg()

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": f"""
你是一个个人记账系统的数据解析助手。

当前日期：{today}
默认货币：SGD
默认地区：Singapore

你的任务：
1. 只根据用户输入提取结构化数据。
2. 不要执行数据库操作。
3. 不要输出解释。
4. 日期必须输出 YYYY-MM-DD。
5. 如果用户说“今天”，使用当前日期。
6. 如果用户说“这个月”，需要转换成当月起止日期。
7. 如果信息缺失，按 schema 要求返回 null 或合理默认值。

具体任务：
{instruction}
"""
            },
            {
                "role": "user",
                "content": content
            }
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": schema
            }
        }
    )

    message = response.choices[0].message

    if getattr(message, "refusal", None):
        raise RuntimeError(f"AI refused: {message.refusal}")

    return json.loads(message.content)

# 返回给AI的信息包括：当前的结构输出，schema，操作类型，新的修改意见；期望AI返回新的结构输出
def revise_payload_with_ai(action_type: str, current_payload: dict, revision_text: str) -> dict:
    if action_type == "add":
        schema = ADD_SCHEMA
        schema_name = "revise_add_expense"
        instruction = "根据用户的修改意见，修改当前新增账单 payload。不要执行数据库操作。"

    elif action_type == "query":
        schema = QUERY_SCHEMA
        schema_name = "revise_query_expense"
        instruction = "根据用户的修改意见，修改当前查询条件 payload。不要执行数据库操作。"

    elif action_type == "summary":
        schema = SUMMARY_SCHEMA
        schema_name = "revise_summary_expense"
        instruction = "根据用户的修改意见，修改当前汇总条件 payload。不要执行数据库操作。"

    elif action_type == "update":
        schema = UPDATE_SCHEMA
        schema_name = "revise_update_expense"
        instruction = "根据用户的修改意见，修改当前更新操作 payload。不要执行数据库操作。"

    else:
        raise ValueError(f"Unsupported action_type: {action_type}")

    content = f"""
当前操作类型：
{action_type}

当前结构化数据：
{json.dumps(current_payload, ensure_ascii=False, indent=2)}

用户修改意见：
{revision_text}

请输出修改后的完整结构化数据。
"""
    return call_ai_parser(
        content=content,
        schema_name=schema_name,
        schema=schema,
        instruction=instruction
    )

def parse_add_with_ai(content: str) -> dict:
    return call_ai_parser(
        content=content,
        schema_name="add_expense",
        schema=ADD_SCHEMA,
        instruction="把用户输入解析成一条新增支出记录。"
    )


def parse_query_with_ai(content: str) -> dict:
    return call_ai_parser(
        content=content,
        schema_name="query_expense",
        schema=QUERY_SCHEMA,
        instruction="把用户输入解析成账单查询条件。limit 默认 20，最大 50。"
    )


def parse_summary_with_ai(content: str) -> dict:
    return call_ai_parser(
        content=content,
        schema_name="summary_expense",
        schema=SUMMARY_SCHEMA,
        instruction="把用户输入解析成账单汇总条件。group_by 只能是 category 或 date。"
    )


def parse_update_with_ai(content: str) -> dict:
    return call_ai_parser(
        content=content,
        schema_name="update_expense",
        schema=UPDATE_SCHEMA,
        instruction="把用户输入解析成修改已有账单的操作。transaction_id 如果用户没提供，返回 null。fields 里不修改的字段返回 null。"
    )