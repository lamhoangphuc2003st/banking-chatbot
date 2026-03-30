import uuid
from app.rag.retrieval.qdrant_retriever import QdrantRetriever
from qdrant_client.models import VectorParams, Distance

class SemanticCache:
    def __init__(self):
        self.retriever = QdrantRetriever()
        self.threshold = 0.92
        self.collection = "faq_cache"

        self._ensure_collection()

    def _ensure_collection(self):

        collections = self.retriever.client.get_collections().collections
        names = [c.name for c in collections]

        if self.collection not in names:

            self.retriever.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=3072,  # text-embedding-3-large
                    distance=Distance.COSINE
                )
            )

    def search(self, query):

        results = self.retriever.search(
            query,
            k=1,
            collection=self.collection
        )

        if not results:
            return None

        hit = results[0]

        if hit["score"] < self.threshold:
            return None

        # payload nằm trong text / answer / context tùy retriever
        return (
            hit.get("context")
            or hit.get("answer")
            or hit.get("text")
        )

    def add(self, query, context):

        vector = self.retriever.embed(query)

        self.retriever.client.upsert(
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