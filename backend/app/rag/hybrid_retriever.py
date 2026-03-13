import os
import json
import faiss
import numpy as np
import logging

from sentence_transformers import SentenceTransformer
from app.retrieval.bm25_index import BM25Index


# model nhẹ hơn nhiều
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

CHUNKS_PATH = os.path.join(BASE_DIR, "data", "vietcombank_chunks.json")
FAISS_PATH = os.path.join(BASE_DIR, "data", "faiss_index.bin")

logger = logging.getLogger(__name__)


class HybridRetriever:

    def __init__(self):

        self.model = None
        self.index = None
        self.chunks = None
        self.bm25 = None

        logger.info("HybridRetriever initialized (lazy mode)")

    def load(self):

        if self.model is None:
            logger.info("Loading embedding model...")
            self.model = SentenceTransformer(
                EMBEDDING_MODEL,
                cache_folder="/tmp/hf_cache"
            )

        if self.index is None:
            logger.info("Loading FAISS index...")
            self.index = faiss.read_index(FAISS_PATH)

        if self.chunks is None:
            logger.info("Loading chunks JSON...")
            with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
                self.chunks = json.load(f)

        if self.bm25 is None:
            logger.info("Building BM25 index...")
            self.bm25 = BM25Index(CHUNKS_PATH)

    def embed_query(self, query):

        if self.model is None:
            self.load()

        embedding = self.model.encode(
            [query],
            normalize_embeddings=True
        )

        return np.array(embedding).astype("float32")

    def vector_search(self, query, top_k=5):

        if self.index is None or self.chunks is None:
            self.load()

        q = self.embed_query(query)

        scores, ids = self.index.search(q, top_k)

        results = []

        for score, idx in zip(scores[0], ids[0]):

            if idx >= len(self.chunks):
                continue

            chunk = self.chunks[idx]

            results.append({
                "score": float(score),
                "doc_id": chunk["doc_id"],
                "product_name": chunk["product_name"],
                "text": chunk["text"],
                "metadata": chunk.get("metadata", {})
            })

        return results

    def hybrid_search(self, query, top_k=5):

        if self.bm25 is None:
            self.load()

        vector_results = self.vector_search(query, top_k)
        bm25_results = self.bm25.search(query, top_k)

        merged = {}

        for r in vector_results:
            merged[r["doc_id"]] = r

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