import os
import cohere


class Reranker:

    def __init__(self):

        self.client = cohere.Client(
            os.getenv("COHERE_API_KEY")
        )

    def rerank(self, query, docs, k=5):

        if not docs:
            return []

        documents = [d["text"] for d in docs]

        response = self.client.rerank(
            model="rerank-v3.5",
            query=query,
            documents=documents,
            top_n=k
        )

        ranked_docs = []

        for r in response.results:

            ranked_docs.append(
                docs[r.index]
            )

        return ranked_docs