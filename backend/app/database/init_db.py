import psycopg2
import os
from dotenv import load_dotenv


def get_conn():
    load_dotenv()
    return psycopg2.connect(
        os.getenv("DATABASE_URL"),
        sslmode="require"
    )


# ------------------------
# DROP TABLE
# ------------------------
def drop_table():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    DROP VIEW IF EXISTS rag_logs_summary;
    DROP TABLE IF EXISTS rag_logs;
    """)

    conn.commit()
    cur.close()
    conn.close()

    print("Dropped table")


# ------------------------
# CREATE BASE TABLE
# ------------------------
def create_table():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS rag_logs (
        id SERIAL PRIMARY KEY,
        session_id TEXT,
        query TEXT,
        rewritten TEXT,
        intent TEXT,
        products JSONB,
        queries JSONB,
        retrieved_docs JSONB,
        reranked_docs JSONB,
        final_docs JSONB,
        response TEXT,
        latency_ms INT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    cur.close()
    conn.close()

    print("Created table")


# ------------------------
# RUN MIGRATION FILE
# ------------------------
def run_migration():
    conn = get_conn()
    cur = conn.cursor()

    current_dir = os.path.dirname(__file__)
    sql_path = os.path.join(current_dir, "001_add_latency_columns.sql")

    with open(sql_path, "r", encoding="utf-8") as f:
        sql = f.read()

    cur.execute(sql)

    conn.commit()
    cur.close()
    conn.close()

    print("Migration applied")


# ------------------------
# RESET ALL
# ------------------------
def reset_db():
    drop_table()
    create_table()
    run_migration()
    print("DB reset complete")


if __name__ == "__main__":
    reset_db()