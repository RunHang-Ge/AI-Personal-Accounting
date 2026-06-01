from add_command import execute_add_payload
from query_command import execute_query_payload
from summary_command import execute_summary_payload
from update_command import execute_update_payload


pending_actions = {}


def set_pending_action(chat_id: int, action_type: str, payload: dict, raw_text: str):
    pending_actions[chat_id] = {
        "type": action_type,
        "payload": payload,
        "raw_text": raw_text,
        "revision_history": []
    }


def cancel_pending_action(chat_id: int) -> str:
    if chat_id in pending_actions:
        del pending_actions[chat_id]
        return "已取消本次操作。"

    return "当前没有待取消的操作。"

def has_pending_action(chat_id: int) -> bool:
    return chat_id in pending_actions


def get_pending_action(chat_id: int) -> dict | None:
    return pending_actions.get(chat_id)

# 在某个chat_id后增加revision，每次AI处理时会同时考虑原文和revision
def update_pending_action(chat_id: int, new_payload: dict, revision_text: str):
    if chat_id not in pending_actions:
        return

    pending_actions[chat_id]["payload"] = new_payload

    if "revision_history" not in pending_actions[chat_id]:
        pending_actions[chat_id]["revision_history"] = []

    pending_actions[chat_id]["revision_history"].append(revision_text)


def execute_pending_action(user_id: int, chat_id: int) -> str:
    if chat_id not in pending_actions:
        return "当前没有待确认的操作。"

    action = pending_actions[chat_id]
    action_type = action["type"]
    payload = action["payload"]
    raw_text = action["raw_text"]

    if action_type == "add":
        result = execute_add_payload(user_id, chat_id, payload, raw_text)

    elif action_type == "query":
        result = execute_query_payload(user_id, payload)

    elif action_type == "summary":
        result = execute_summary_payload(user_id, payload)

    elif action_type == "update":
        result = execute_update_payload(user_id, payload)

    else:
        result = "未知操作类型，无法执行。"

    del pending_actions[chat_id]
    return result


def format_preview(action_type: str, payload: dict) -> str:
    if action_type == "add":
        return (
            "请确认以下新增账单：\n\n"
            f"日期：{payload['txn_date']}\n"
            f"类别：{payload['category']}\n"
            f"金额：{payload['currency']} {payload['amount']}\n"
            f"商户：{payload['merchant'] or '-'}\n"
            f"备注：{payload['note'] or '-'}\n\n"
            "输入「确认」执行\n"
            "输入「取消」放弃"
        )

    if action_type == "query":
        return (
            "请确认以下查询条件：\n\n"
            f"类别：{payload['category'] or '不限'}\n"
            f"日期范围：{payload['date_from'] or '不限'} 至 {payload['date_to'] or '不限'}\n"
            f"最低金额：{payload['min_amount'] if payload['min_amount'] is not None else '不限'}\n"
            f"最高金额：{payload['max_amount'] if payload['max_amount'] is not None else '不限'}\n"
            f"货币：{payload['currency'] or '不限'}\n"
            f"商户：{payload['merchant'] or '不限'}\n"
            f"关键词：{payload['keyword'] or '不限'}\n"
            f"返回数量：{payload['limit']}\n\n"
            "输入「确认」执行\n"
            "输入「取消」放弃"
        )

    if action_type == "summary":
        group_by_text = "类别" if payload["group_by"] == "category" else "日期"

        return (
            "请确认以下汇总条件：\n\n"
            f"汇总维度：按{group_by_text}汇总\n"
            f"日期范围：{payload['date_from'] or '不限'} 至 {payload['date_to'] or '不限'}\n"
            f"类别：{payload['category'] or '不限'}\n"
            f"货币：{payload['currency'] or '不限'}\n\n"
            "输入「确认」执行\n"
            "输入「取消」放弃"
        )

    if action_type == "update":
        fields = payload["fields"]
        changed_fields = {
            key: value for key, value in fields.items()
            if value is not None
        }

        if not payload["transaction_id"]:
            target = "未识别到记录 ID"
        else:
            target = f"#{payload['transaction_id']}"

        if not changed_fields:
            change_text = "未识别到需要修改的字段"
        else:
            change_text = "\n".join(
                f"{key}：{value}" for key, value in changed_fields.items()
            )

        return (
            "请确认以下修改操作：\n\n"
            f"目标记录：{target}\n"
            f"修改内容：\n{change_text}\n\n"
            "输入「确认」执行\n"
            "输入「取消」放弃"
        )

    return "无法生成预览。"