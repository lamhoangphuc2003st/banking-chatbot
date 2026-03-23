import os
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

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
    def build_filter(self, products):
        """
        Build Qdrant filter cho multi-product
        """
        if not products:
            return None

        return Filter(
            should=[
                FieldCondition(
                    key="product_name",
                    match=MatchValue(value=p)
                )
                for p in products
            ]
        )

    # -------------------------
    def vector_search(self, query, k=10, products=None):

        vector = self.embed(query)

        query_filter = self.build_filter(products)

        logger.info(f"[Qdrant] Query: {query}")
        logger.info(f"[Qdrant] Products filter: {products}")

        results = self.client.query_points(
            collection_name=self.collection,
            query=vector,
            limit=k,
            query_filter=query_filter
        )

        docs = []

        for r in results.points:
            payload = r.payload or {}

            docs.append({
                "doc_id": payload.get("doc_id", "unknown"),
                "text": payload.get("text", ""),
                "product_name": payload.get("product_name")
            })

        return docs

    # -------------------------
    def search(self, query, k=20, products=None):
        """
        Main search entry
        """

        try:
            docs = self.vector_search(
                query,
                k=k,
                products=products
            )

            return docs

        except Exception as e:
            logger.exception("[Qdrant] Search error")
            return []