import json
import faiss
import numpy as np
import os

from langchain_openai import OpenAIEmbeddings


# -------------------------
# Path setup
# -------------------------

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

DATA_DIR = os.path.join(BASE_DIR, "data")

CHUNKS_PATH = os.path.join(DATA_DIR, "vietcombank_chunks.json")
INDEX_PATH = os.path.join(DATA_DIR, "faiss_index.bin")


# -------------------------
# Embedding model
# -------------------------

emb = OpenAIEmbeddings(
    model="text-embedding-3-large"
)


# -------------------------
# Load chunks
# -------------------------

with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
    chunks = json.load(f)


vectors = []

for c in chunks:

    v = emb.embed_query(c["text"])

    vectors.append(v)


vectors = np.array(vectors).astype("float32")


# -------------------------
# Build FAISS
# -------------------------

index = faiss.IndexFlatL2(len(vectors[0]))

index.add(vectors)


faiss.write_index(
    index,
    INDEX_PATH
)

print("FAISS index built successfully")