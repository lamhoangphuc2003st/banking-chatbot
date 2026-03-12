import json
from rank_bm25 import BM25Okapi


class BM25Index:

    def __init__(self, chunks_path):

        with open(chunks_path, "r", encoding="utf-8") as f:
            self.chunks = json.load(f)

        corpus = [c["text"] for c in self.chunks]

        tokenized_corpus = [doc.split() for doc in corpus]

        self.bm25 = BM25Okapi(tokenized_corpus)

    def search(self, query, top_k=10):

        tokenized_query = query.split()

        scores = self.bm25.get_scores(tokenized_query)

        ranked = sorted(
            list(enumerate(scores)),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]

        results = []

        for idx, score in ranked:

            chunk = self.chunks[idx]

            results.append({
                "score": float(score),
                "doc_id": chunk["doc_id"],
                "product_name": chunk["product_name"],
                "text": chunk["text"],
                "metadata": chunk.get("metadata", {})
            })

        return results