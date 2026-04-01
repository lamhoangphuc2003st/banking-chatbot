import os

from qdrant_client import AsyncQdrantClient
from langchain_openai import OpenAIEmbeddings

from app.rag.utils.logger import get_logger

logger = get_logger(__name__)


class QdrantRetriever:

    def __init__(self):
        self.client = AsyncQdrantClient(
            url=os.getenv("QDRANT_CLOUD_URL"),
            api_key=os.getenv("QDRANT_CLOUD_API_KEY"),
            prefer_grpc=False,
            timeout=60,
            check_compatibility=False
        )
        self.collection = "vietcombank"

        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-large"
        )

    async def embed(self, query: str) -> list:
        return await self.embeddings.aembed_query(query)

    async def _query_qdrant(self, vector: list, k: int, collection: str = None) -> list:
        """Gửi vector đến Qdrant và trả về docs. Không tự embed."""
        results = await self.client.query_points(
            collection_name=collection or self.collection,
            query=vector,
            limit=k,
            with_payload=True,
            with_vectors=False
        )
        docs = []
        for r in results.points:
            payload = r.payload or {}
            docs.append({
                "score": r.score,
                "doc_id": payload.get("doc_id", "unknown"),
                "text": payload.get("text"),
                "context": payload.get("context"),
                "answer": payload.get("answer"),
            })
        return docs

    async def vector_search(self, query: str, k: int = 10, collection: str = None) -> list:
        vector = await self.embed(query)
        logger.info(f"[Qdrant] Query: {query}")
        return await self._query_qdrant(vector, k=k, collection=collection)

    async def search_with_vector(self, vector: list, k: int = 20, collection: str = None) -> list:
        """Tìm kiếm dùng vector đã embed sẵn — bỏ qua bước gọi OpenAI."""
        try:
            return await self._query_qdrant(vector, k=k, collection=collection)
        except Exception:
            logger.exception("[Qdrant] search_with_vector error")
            return []

    async def search(self, query: str, k: int = 20, collection: str = None) -> list:
        try:
            return await self.vector_search(query, k=k, collection=collection)
        except Exception:
            logger.exception("[Qdrant] Search error")
            return []