import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

CHUNKS_PATH = "backend/data/vietcombank_chunks.json"
FAISS_PATH = "backend/data/faiss_index.bin"

model = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
    chunks = json.load(f)

texts = [c["text"] for c in chunks]

embeddings = model.encode(
    texts,
    normalize_embeddings=True,
    show_progress_bar=True
)

embeddings = np.array(embeddings).astype("float32")

dim = embeddings.shape[1]

index = faiss.IndexFlatIP(dim)

index.add(embeddings)

faiss.write_index(index, FAISS_PATH)

print("FAISS index rebuilt")