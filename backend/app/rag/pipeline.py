from app.rag.chains.rewrite_chain import rewrite_chain
from app.rag.chains.multi_query_chain import multi_query_chain
from app.rag.chains.generator_chain import generator_chain

from app.rag.retrieval.hybrid_retriever import HybridRetriever
from app.rag.retrieval.reranker import Reranker

from app.rag.routers.product_router import detect_product
from app.rag.utils.context_builder import build_context
from app.rag.utils.logger import get_logger


logger = get_logger(__name__)


class RAGPipeline:

    def __init__(self):

        logger.info("Initializing RAGPipeline")

        self.retriever = HybridRetriever(
            "data/vietcombank_chunks.json",
            "data/faiss_index.bin"
        )

        self.reranker = Reranker()

        self.retrieve_top_k = 15
        self.rerank_top_k = 5

        self.products = self.load_products()

    # -------------------------
    # Load products
    # -------------------------
    def load_products(self):

        import json

        with open("data/vietcombank_chunks.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        products = set()

        for d in data:

            p = d.get("product_name")

            if p:
                products.add(p)

        return list(products)

    # -------------------------
    # Retrieval
    # -------------------------
    def retrieve(self, queries):

        logger.info(f"Retrieving {len(queries)} queries")

        docs = []

        for q in queries:

            results = self.retriever.search(q)

            docs.extend(results)

        # deduplicate by doc_id
        merged = {}

        for d in docs:

            key = d["doc_id"]

            if key not in merged:
                merged[key] = d

        docs = list(merged.values())

        logger.info(f"Retrieved docs: {len(docs)}")

        return docs

    # -------------------------
    # Product filtering
    # -------------------------
    def filter_products(self, docs, products):

        if not products:
            return docs

        filtered = []

        for d in docs:

            name = (d.get("product_name") or "").lower()

            for p in products:

                if p.lower() in name:
                    filtered.append(d)
                    break

        if filtered:
            logger.info(f"Product filtered docs: {len(filtered)}")
            return filtered

        logger.warning("Product filter empty → fallback")

        return docs

    # -------------------------
    # Main ask
    # -------------------------
    def ask(self, query, history=None):

        logger.info(f"User query: {query}")

        # -------------------------
        # Rewrite
        # -------------------------
        rewritten = rewrite_chain.invoke({
            "query": query,
            "history": history
        })

        logger.info(f"Rewrite: {rewritten}")

        # -------------------------
        # Product router
        # -------------------------
        products = detect_product(
            rewritten,
            self.products
        )

        logger.info(f"Products: {products}")

        # -------------------------
        # Multi query
        # -------------------------
        multi_queries = multi_query_chain.invoke({
            "query": rewritten
        })

        queries = list(dict.fromkeys(
            [rewritten] + multi_queries
        ))

        logger.info(f"Search queries: {queries}")

        # -------------------------
        # Retrieval
        # -------------------------
        docs = self.retrieve(queries)

        # -------------------------
        # Product filter
        # -------------------------
        docs = self.filter_products(
            docs,
            products
        )

        # -------------------------
        # Rerank
        # -------------------------
        docs = self.reranker.rerank(
            rewritten,
            docs,
            k=self.rerank_top_k
        )

        # -------------------------
        # Context
        # -------------------------
        context = build_context(docs)

        # -------------------------
        # Generate answer
        # -------------------------
        result = generator_chain.invoke({
            "context": context,
            "question": query
        })

        return result.content