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

cur.execute("SELECT * FROM rag_logs ORDER BY created_at DESC")

cols = [desc[0] for desc in cur.description]

rows = cur.fetchall()

for row in rows:
    print("\n====================")
    for col, val in zip(cols, row):
        print(f"{col}: {shorten(val, 300)}")



cur.close()
conn.close()