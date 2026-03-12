import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer


class Retriever:

    def __init__(
        self,
        index_path="../data/faiss_index.bin",
        chunks_path="../data/vietcombank_chunks.json",
        model_name="bkai-foundation-models/vietnamese-bi-encoder"
    ):

        self.index = faiss.read_index(index_path)

        with open(chunks_path, "r", encoding="utf-8") as f:
            self.chunks = json.load(f)

        self.model = SentenceTransformer(model_name)

    def embed_query(self, query):

        emb = self.model.encode(
            [query],
            normalize_embeddings=True
        )

        return np.array(emb).astype("float32")

    def retrieve(self, query, top_k=10):

        query_vec = self.embed_query(query)

        scores, ids = self.index.search(query_vec, top_k)

        results = []

        for score, idx in zip(scores[0], ids[0]):

            chunk = self.chunks[idx]

            results.append({
                "score": float(score),
                "text": chunk["text"],
                "product_name": chunk.get("product_name"),
                "metadata": chunk.get("metadata")
            })

        return results