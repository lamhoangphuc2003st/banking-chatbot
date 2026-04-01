import uuid

from qdrant_client.models import VectorParams, Distance

from app.rag.retrieval.qdrant_retriever import QdrantRetriever


class SemanticCache:

    def __init__(self):
        self.retriever = QdrantRetriever()
        self.threshold = 0.92
        self.collection = "faq_cache"
        # Lazy init — _ensure_collection() được gọi lần đầu khi search/add
        self._ready = False

    async def _ensure_collection(self):
        """Tạo collection nếu chưa tồn tại. Chỉ chạy 1 lần."""
        if self._ready:
            return

        collections = await self.retriever.client.get_collections()
        names = [c.name for c in collections.collections]

        if self.collection not in names:
            await self.retriever.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=3072,
                    distance=Distance.COSINE
                )
            )

        self._ready = True

    def _extract_hit(self, results: list):
        """Lấy context từ kết quả tìm kiếm nếu vượt threshold."""
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
        """Tìm kiếm bằng text — tự embed query."""
        await self._ensure_collection()
        results = await self.retriever.search(query, k=1, collection=self.collection)
        return self._extract_hit(results)

    async def search_with_vector(self, vector: list):
        """Tìm kiếm bằng vector đã embed sẵn — tránh gọi OpenAI lần 2."""
        await self._ensure_collection()
        results = await self.retriever.search_with_vector(
            vector, k=1, collection=self.collection
        )
        return self._extract_hit(results)

    async def add(self, query: str, context: str):
        await self._ensure_collection()

        vector = await self.retriever.embed(query)

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