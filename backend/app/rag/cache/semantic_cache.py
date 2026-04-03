import asyncio
import uuid

from qdrant_client.models import VectorParams, Distance

from app.rag.retrieval.qdrant_retriever import QdrantRetriever


class SemanticCache:

    def __init__(self, retriever: QdrantRetriever = None):
        # FIX 1: nhận retriever từ bên ngoài thay vì tạo mới
        # → dùng chung connection pool với pipeline, tránh cold TCP trên request đầu
        self.retriever = retriever or QdrantRetriever()
        self.threshold = 0.92
        self.collection = "faq_cache"
        self._ready = False
        # FIX 4: Lock ngăn race condition khi nhiều sub_queries gọi đồng thời
        self._init_lock = asyncio.Lock()

    async def _ensure_collection(self):
        if self._ready:
            return

        async with self._init_lock:
            if self._ready:
                return

            try:
                await self.retriever.client.get_collection(self.collection)
            except Exception:
                await self.retriever.client.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(
                        size=3072,
                        distance=Distance.COSINE
                    )
                )

            self._ready = True

    def _extract_hit(self, results: list):
        if not results:
            return None
        hit = results[0]
        if hit["score"] < self.threshold:
            return None
        return (
            hit.get("context")
            or hit.get("answer")
            or hit.get("text")
        )

    async def search(self, query: str):
        await self._ensure_collection()
        results = await self.retriever.search(query, k=1, collection=self.collection)
        return self._extract_hit(results)

    async def search_with_vector(self, vector: list):
        await self._ensure_collection()
        try:
            results = await self.retriever.search_with_vector(
                vector, k=1, collection=self.collection
            )
        except Exception:
            return None

        return self._extract_hit(results)

    async def add(self, query: str, context: str):
        """Embed query rồi upsert — dùng khi không có sẵn vector."""
        await self._ensure_collection()
        vector = await self.retriever.embed(query)
        await self._upsert(query, context, vector)

    async def add_with_vector(self, query: str, context: str, vector: list):
        """FIX 3: upsert với vector đã tính sẵn — tránh gọi OpenAI lần 2."""
        try:
            await self._ensure_collection()
            await self._upsert(query, context, vector)
        except Exception:
            pass

    async def _upsert(self, query: str, context: str, vector: list):
        await self.retriever.client.upsert(
            collection_name=self.collection,
            points=[{
                "id": str(uuid.uuid4()),
                "vector": vector,
                "payload": {
                    "query": query,
                    "context": context
                }
            }]
        )