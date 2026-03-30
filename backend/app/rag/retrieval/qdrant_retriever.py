import os
from qdrant_client import QdrantClient

from langchain_openai import OpenAIEmbeddings

from app.rag.utils.logger import get_logger

logger = get_logger(__name__)


class QdrantRetriever:

    def __init__(self):

        self.client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            port=None,
            prefer_grpc=False,
            timeout=60
        )
        self.collection = "vietcombank"

        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-large"
        )

    # -------------------------
    def embed(self, query):
        return self.embeddings.embed_query(query)

    # -------------------------
    def vector_search(self, query, k=10, collection=None):

        vector = self.embed(query)

        logger.info(f"[Qdrant] Query: {query}")

        results = self.client.query_points(
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

    # -------------------------
    def search(self, query, k=20, collection=None):

        try:
            docs = self.vector_search(query, k=k, collection=collection)

            return docs

        except Exception as e:
            logger.exception("[Qdrant] Search error")
            return []