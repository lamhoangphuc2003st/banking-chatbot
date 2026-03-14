from sentence_transformers import CrossEncoder


class Reranker:

    def __init__(self):

        self.model = CrossEncoder(
            "BAAI/bge-reranker-base"
        )

    def rerank(self, query, docs, k=5):

        pairs = [[query, d["text"]] for d in docs]

        scores = self.model.predict(pairs)

        ranked = list(zip(docs, scores))

        ranked.sort(
            key=lambda x: x[1],
            reverse=True
        )

        return [d for d,_ in ranked[:k]]