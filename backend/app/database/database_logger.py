import json
from app.database.connection import get_connection

def save_rag_log(data):

    conn = get_connection()
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
    cur.execute("""
        INSERT INTO rag_logs (
            session_id, query, rewritten, intent,
            products, queries, retrieved_docs,
            reranked_docs, final_docs,
            response, latency_ms
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        data.get("session_id"),
        data.get("query"),
        data.get("rewritten"),
        data.get("intent"),
        json.dumps(data.get("products")),
        json.dumps(data.get("queries")),
        json.dumps(data.get("retrieved_docs")),
        json.dumps(data.get("reranked_docs")),
        json.dumps(data.get("final_docs")),
        data.get("response"),
        data.get("latency_ms")
    ))

    conn.commit()
    cur.close()
    conn.close()