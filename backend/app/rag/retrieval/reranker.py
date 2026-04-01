import os
import cohere


class Reranker:
    def __init__(self):
        # cohere.AsyncClient — drop-in async replacement for cohere.Client
        self.client = cohere.AsyncClient(
            os.getenv("COHERE_API_KEY")
        )

    async def rerank(self, query: str, docs: list, k: int = 5) -> list:
        if not docs:
            return []

        documents = [d["text"] for d in docs]

        response = await self.client.rerank(
            model="rerank-v3.5",
            query=query,
            documents=documents,
            top_n=k
        )

        return [docs[r.index] for r in response.results]