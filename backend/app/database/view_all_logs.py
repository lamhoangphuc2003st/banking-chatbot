import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def shorten(text, max_len=120):
    if not text:
        return ""
    text = str(text).replace("\n", " ")
    return text[:max_len] + "..." if len(text) > max_len else text


conn = psycopg2.connect(
    os.getenv("DATABASE_URL"),
    sslmode="require"
)

cur = conn.cursor()

cur.execute("""
    SELECT *
    FROM rag_logs
    ORDER BY created_at DESC
    LIMIT 5
""")

rows = cur.fetchall()

for r in rows:
    print("\n====================")
    print("ID:", r[0])
    print("Session:", shorten(r[1], 300))
    print("Query:", shorten(r[2], 300))
    print("Rewrite:", shorten(r[3], 300))
    print("Intent:", r[4])
    print("Products:", shorten(r[5], 300))
    print("Queries:", shorten(r[6], 300))
    print("Retrieved:", shorten(r[7], 1000))
    print("Reranked:", shorten(r[8], 300))
    print("Final Docs:", shorten(r[9], 300))
    print("Response:", shorten(r[10], 300))
    print("Latency:", r[11], "ms")
    print("Time:", r[12])

cur.close()
conn.close()