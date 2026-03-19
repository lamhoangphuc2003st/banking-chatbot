import psycopg2
import os
from dotenv import load_dotenv

def init_db():
    load_dotenv()

    conn = psycopg2.connect(
        os.getenv("DATABASE_URL"),
        sslmode="require"
    )

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

    print("Table created")