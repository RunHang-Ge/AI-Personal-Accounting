# AI-Personal-Accounting

main.py
- 接收 Telegram 消息
- 判断命令类型
- 调用 AI parser
- 存入 pending action
- 处理确认/取消

ai_parser.py
- 把自然语言转成结构化 payload

pending_action.py
- 暂存待确认操作
- 确认后执行对应 execute 函数

add_command.py
- execute_add_payload()
- save_transaction()

query_command.py
- execute_query_payload()

summary_command.py
- execute_summary_payload()

update_command.py
- execute_update_payload()

db.py
- get_db_connection()
- init_db()
