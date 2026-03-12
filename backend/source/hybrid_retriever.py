import os
import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from bm25_index import BM25Index


EMBEDDING_MODEL = "bkai-foundation-models/vietnamese-bi-encoder"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHUNKS_PATH = os.path.join(BASE_DIR, "data/vietcombank_chunks.json")
FAISS_PATH = os.path.join(BASE_DIR, "data/faiss_index.bin")


class HybridRetriever:

    def __init__(self):

        self.model = SentenceTransformer(EMBEDDING_MODEL)

        self.index = faiss.read_index(FAISS_PATH)

        with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
            self.chunks = json.load(f)

        self.bm25 = BM25Index(CHUNKS_PATH)

    def embed_query(self, query):

        embedding = self.model.encode(
            [query],
            normalize_embeddings=True
        )

        return np.array(embedding).astype("float32")

    def vector_search(self, query, top_k=10):

        q = self.embed_query(query)

        scores, ids = self.index.search(q, top_k)

        results = []

        for score, idx in zip(scores[0], ids[0]):

            chunk = self.chunks[idx]

            results.append({
                "score": float(score),
                "doc_id": chunk["doc_id"],
                "product_name": chunk["product_name"],
                "text": chunk["text"],
                "metadata": chunk.get("metadata", {})
            })

        return results

    def hybrid_search(self, query, top_k=10):

        vector_results = self.vector_search(query, top_k)

        bm25_results = self.bm25.search(query, top_k)

        merged = {}

        for r in vector_results:

            key = r["doc_id"]

            merged[key] = r

        for r in bm25_results:

            key = r["doc_id"]

            if key in merged:

                merged[key]["score"] += r["score"]

            else:

                merged[key] = r

        ranked = sorted(
            merged.values(),
            key=lambda x: x["score"],
            reverse=True
        )

        return ranked[:top_k]