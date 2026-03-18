import json
import os
import time
import requests

from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct
from langchain_openai import OpenAIEmbeddings

COLLECTION_NAME = "vietcombank"

# -------------------------
# WAKE UP QDRANT (fix sleep Render)
# -------------------------
print("Waking up Qdrant...")

for i in range(10):
    try:
        res = requests.get(QDRANT_URL, timeout=10)
        if res.status_code == 200:
            print("Qdrant is awake!")
            break
    except Exception:
        print(f"Retry {i+1}/10...")
        time.sleep(5)
else:
    raise Exception("❌ Cannot connect to Qdrant")

# -------------------------
# INIT CLIENT
# -------------------------
client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    port=None,              # đừng set port
    prefer_grpc=False,      # cực kỳ quan trọng
    timeout=60
)


# test connection (safe)
try:
    print(client.get_collections())
except Exception as e:
    print("⚠️ Cannot get collections:", e)

# -------------------------
# EMBEDDING
# -------------------------
emb = OpenAIEmbeddings(
    model="text-embedding-3-large"
)

# -------------------------
# LOAD DATA
# -------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
file_path = os.path.join(BASE_DIR, "data", "vietcombank_chunks.json")

with open(file_path, "r", encoding="utf-8") as f:
    chunks = json.load(f)

# -------------------------
# CREATE COLLECTION
# -------------------------
if not client.collection_exists(COLLECTION_NAME):

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=3072,
            distance=Distance.COSINE
        )
    )
    print("Collection created!")

    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="product_name",
        field_schema="keyword"
    )
    print("Index product_name created!")

else:
    print("Collection already exists")

    try:
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="product_name",
            field_schema="keyword"
        )
        print("Index ensured!")
    except Exception:
        print("Index already exists")

# -------------------------
# EMBED ALL TEXT (FAST)
# -------------------------
texts = [c["text"] for c in chunks]

print("Embedding all texts...")
vectors = emb.embed_documents(texts)

# -------------------------
# INSERT DATA (BATCH)
# -------------------------
BATCH_SIZE = 64
points = []

for i, (c, vector) in enumerate(zip(chunks, vectors)):

    payload = {
        "doc_id": c.get("doc_id"),
        "text": c.get("text"),
        "product_name": c.get("product_name"),
        "product_type": c.get("product_type"),
    }

    points.append(
        PointStruct(
            id=i,
            vector=vector,
            payload=payload
        )
    )

    if len(points) >= BATCH_SIZE:
        try:
            client.upsert(
                collection_name=COLLECTION_NAME,
                points=points
            )
            print(f"Inserted batch {i}")
        except Exception as e:
            print("❌ Upsert failed:", e)

        points = []

# insert remaining
if points:
    try:
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points
        )
        print("Inserted final batch")
    except Exception as e:
        print("❌ Final upsert failed:", e)

print("✅ Qdrant ingest done!")