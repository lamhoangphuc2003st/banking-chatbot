import json
from app.database.connection import get_connection
from app.rag.utils.logger import get_logger

logger = get_logger(__name__)


def save_rag_log(data: dict):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO rag_logs (
                session_id, query, rewritten, intent,
                mentioned_products, queries,
                retrieved_docs, reranked_docs, final_docs,
                response, latency_ms,
                retrieval_latency_ms, cache_type,
                clarification, decomposed,
                latency_breakdown, error
            )
            VALUES (%s,%s,%s,%s, %s,%s, %s,%s,%s, %s,%s, %s,%s, %s,%s, %s,%s)
        """, (
            data.get("session_id"),
            data.get("query"),
            data.get("rewritten"),
            data.get("intent"),
            _to_json(data.get("mentioned_products")),
            _to_json(data.get("queries")),
            _to_json(data.get("retrieved_docs")),
            _to_json(data.get("reranked_docs")),
            _to_json(data.get("final_docs")),
            data.get("response"),
            data.get("latency_ms"),
            data.get("retrieval_latency_ms"),
            data.get("cache_type"),
            bool(data.get("clarification")),
            _to_json(data.get("decomposed")),
            _to_json(data.get("latency_breakdown")),
            data.get("error"),
        ))
        conn.commit()
        cur.close()
    except Exception:
        logger.exception("save_rag_log failed")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def _to_json(value) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)