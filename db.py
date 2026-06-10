import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    return psycopg2.connect(DATABASE_URL)


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            telegram_user_id BIGINT NOT NULL,
            telegram_chat_id BIGINT NOT NULL,
            txn_date DATE NOT NULL,
            category TEXT NOT NULL,
            amount NUMERIC(12, 2) NOT NULL,
            currency TEXT NOT NULL,
            merchant TEXT,
            note TEXT,
            raw_text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)

    conn.commit()
    cur.close()
    conn.close()


def migrate_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        ALTER TABLE transactions
        ADD COLUMN IF NOT EXISTS google_map TEXT;
    """)

    conn.commit()
    cur.close()
    conn.close()