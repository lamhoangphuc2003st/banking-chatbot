from typing import Generator
import time
import uuid

from app.rag.chains.rewrite_chain import rewrite_chain
from app.rag.chains.multi_query_chain import multi_query_chain
from app.rag.chains.generator_chain import generator_chain

from app.rag.retrieval.hybrid_retriever import HybridRetriever
from app.rag.retrieval.reranker import Reranker
from app.rag.retrieval.compression import ContextCompressor

from app.rag.routers.product_router import detect_product
from app.rag.routers.intent_router import detect_intent

from app.rag.utils.context_builder import build_context
from app.rag.utils.logger import get_logger

from app.database.database_logger import save_rag_log

logger = get_logger(__name__)


class RAGPipeline:

    def __init__(self):

        logger.info("Initializing RAGPipeline")

        self.retriever = HybridRetriever(
            "data/vietcombank_chunks.json",
            "data/faiss_index.bin"
        )

        # reranker
        self.reranker = Reranker()

        # context compressor
        self.compressor = ContextCompressor()

        self.retrieve_top_k = 15
        self.final_top_k = 5

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
        seen = set()

        for q in queries:

            results = self.retriever.search(q)

            for d in results:

                doc_id = d["doc_id"]

                if doc_id not in seen:
                    seen.add(doc_id)
                    docs.append(d)

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
    # Rerank
    # -------------------------
    def rerank(self, query, docs):

        if not docs:
            return docs

        docs = docs[:30]

        logger.info(f"Reranking {len(docs)} docs")

        docs = self.reranker.rerank(
            query,
            docs,
            k=self.final_top_k
        )

        return docs

    # -------------------------
    # Streaming answer
    # -------------------------
    def stream(self, query, history=None, session_id=None) -> Generator[str, None, None]:

        start_time = time.time()
        session_id = session_id or str(uuid.uuid4())

        trace = {
            "session_id": session_id,
            "query": query,
            "history": history
        }

        full_response = ""

        try:
            logger.info(f"User query: {query}")

            # -------------------------
            # Intent
            # -------------------------
            intent = detect_intent(query)
            trace["intent"] = intent

            if intent == "CHAT":

                stream = generator_chain.stream({
                    "context": "",
                    "question": query
                })

                for chunk in stream:
                    if chunk.content:
                        full_response += chunk.content
                        yield chunk.content

                trace["response"] = full_response
                trace["latency_ms"] = int((time.time() - start_time) * 1000)

                save_rag_log(trace)
                return

            # -------------------------
            # Rewrite
            # -------------------------
            rewritten = rewrite_chain.invoke({
                "query": query,
                "history": history
            })

            trace["rewritten"] = rewritten

            # -------------------------
            # Product
            # -------------------------
            products = detect_product(
                rewritten,
                self.products
            )

            trace["products"] = products

            # -------------------------
            # Multi query
            # -------------------------
            multi_queries = multi_query_chain.invoke({
                "query": rewritten
            })

            queries = list(dict.fromkeys(
                [rewritten] + multi_queries
            ))

            trace["queries"] = queries

            # -------------------------
            # Retrieval
            # -------------------------
            docs = self.retrieve(queries)

            trace["retrieved_docs"] = [
                d["doc_id"] for d in docs
            ]

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
            docs = self.rerank(
                rewritten,
                docs
            )

            trace["reranked_docs"] = [
                d["doc_id"] for d in docs
            ]

            # -------------------------
            # Context compression
            # -------------------------
            docs = self.compressor.compress(docs)

            trace["final_docs"] = [
                d["doc_id"] for d in docs
            ]

            # -------------------------
            # Context
            # -------------------------
            context = build_context(docs)

            # -------------------------
            # Generate (STREAM)
            # -------------------------
            stream = generator_chain.stream({
                "context": context,
                "question": query
            })

            for chunk in stream:
                if chunk.content:
                    full_response += chunk.content
                    yield chunk.content

            # -------------------------
            # SAVE LOG
            # -------------------------
            trace["response"] = full_response
            trace["latency_ms"] = int((time.time() - start_time) * 1000)

            save_rag_log(trace)

        except Exception as e:
            trace["error"] = str(e)
            save_rag_log(trace)
            raise