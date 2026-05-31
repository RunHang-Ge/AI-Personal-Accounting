import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg2.connect(DATABASE_URL)


def get_all_user_tables(conn):
    """
    获取所有非系统表
    """
    sql = """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
          AND table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name;
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql)
        return cur.fetchall()


def get_table_columns(conn, table_schema, table_name):
    """
    获取字段名称和字段类型
    """
    sql = """
        SELECT
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
        ORDER BY ordinal_position;
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (table_schema, table_name))
        return cur.fetchall()


def get_table_row_count(conn, table_schema, table_name):
    """
    获取表的数据条数
    """
    sql = f'SELECT COUNT(*) FROM "{table_schema}"."{table_name}";'

    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchone()[0]


def inspect_database():
    conn = get_db_connection()

    try:
        tables = get_all_user_tables(conn)
        result = []

        for table in tables:
            table_schema = table["table_schema"]
            table_name = table["table_name"]

            row_count = get_table_row_count(conn, table_schema, table_name)
            columns = get_table_columns(conn, table_schema, table_name)

            result.append({
                "table_schema": table_schema,
                "table_name": table_name,
                "row_count": row_count,
                "created_at": "N/A",
                "columns": [
                    {
                        "column_name": col["column_name"],
                        "data_type": col["data_type"],
                        "is_nullable": col["is_nullable"],
                        "column_default": col["column_default"],
                    }
                    for col in columns
                ]
            })

        return result

    finally:
        conn.close()


def print_database_info():
    db_info = inspect_database()

    if not db_info:
        print("No user tables found.")
        return

    for table in db_info:
        print("=" * 80)
        print(f"Table: {table['table_schema']}.{table['table_name']}")
        print(f"Rows: {table['row_count']}")
        print(f"Created At: {table['created_at']}")
        print("-" * 80)

        for col in table["columns"]:
            print(
                f"{col['column_name']} | "
                f"{col['data_type']} | "
                f"nullable={col['is_nullable']} | "
                f"default={col['column_default']}"
            )

    print("=" * 80)


if __name__ == "__main__":
    print_database_info()