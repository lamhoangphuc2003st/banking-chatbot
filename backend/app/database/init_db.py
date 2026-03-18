import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
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