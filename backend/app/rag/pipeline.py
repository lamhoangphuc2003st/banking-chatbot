from typing import Generator
import time
import uuid

from app.rag.chains.rewrite_chain import rewrite_chain
from app.rag.chains.multi_query_chain import multi_query_chain
from app.rag.chains.generator_chain import generator_chain
from app.rag.chains.decompose_chain import decompose_chain

from app.rag.retrieval.qdrant_retriever import QdrantRetriever
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
        logger.info("Initializing Async RAGPipeline")

        self.retriever = QdrantRetriever()

        self.reranker = Reranker()
        self.compressor = ContextCompressor()

        self.retrieve_top_k = 15
        self.final_top_k = 5

        self.products = self.load_products()

    # -------------------------
    def load_products(self):
        import json

        with open("data/vietcombank_chunks.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        products = set()

        for d in data:
            name = d.get("metadata", {}).get("product_name")

            if name:
                name = name.strip()  # remove space
                name = " ".join(name.split())  # normalize whitespace

                products.add(name)

        products = sorted(list(products))  # 🔥 FIX: stable order

        logger.info(f"Loaded {len(products)} products")
        logger.info(f"Products: {products}")  # debug

        return products

    # -------------------------
    def retrieve(self, queries, products):

        logger.info(f"Retrieving {len(queries)} queries...")
        t0 = time.time()

        docs = []
        seen = set()

        for q in queries:
            results = self.retriever.search(q, self.retrieve_top_k, products)

            for d in results:
                doc_id = d["doc_id"]
                if doc_id not in seen:
                    seen.add(doc_id)
                    docs.append(d)

        logger.info(f"Retrieved {len(docs)} unique docs in {(time.time()-t0):.2f}s")
        return docs

    # -------------------------
    def rerank(self, query, docs, top_k=None):

        if not docs:
            return docs

        docs = docs[:30]

        k = top_k or self.final_top_k

        logger.info(f"Reranking {len(docs)} docs...")
        t0 = time.time()

        results = self.reranker.rerank(query, docs, k=k)

        logger.info(f"Reranked to {len(results)} docs in {(time.time()-t0):.2f}s")
        return results

    # -------------------------
    def pipeline(self, query, history):

        # Rewrite
        t0 = time.time()
        rewritten = rewrite_chain.invoke({
            "query": query,
            "history": history
        })
        logger.info(f"Rewrite: {rewritten} ({(time.time()-t0):.2f}s)")

        # Decompose
        t0
        decomposed = decompose_chain.invoke({
            "query": rewritten
        })
        logger.info(f"Decomposed: {decomposed} ({(time.time()-t0):.2f}s)")

        if not isinstance(decomposed, list):
            decomposed = [rewritten]

        # =========================
        # CASE 1: KHÔNG DECOMPOSE
        # =========================
        if len(decomposed) <= 1:

            # Multi-query
            t0 = time.time()
            multi_queries = multi_query_chain.invoke({"query": rewritten})
            queries = list(dict.fromkeys([rewritten] + multi_queries))

            logger.info(f"Multi-query: {queries} ({(time.time()-t0):.2f}s)")

            # Product filter
            t0 = time.time()
            products = detect_product(rewritten, self.products)
            
            if products == []:
                products = None

            logger.info(f"Detected products: {products} ({(time.time()-t0):.2f}s)")

            # Retrieve
            docs = self.retrieve(queries, products)
            retrieved_docs = docs.copy()

            # Rerank
            docs = self.rerank(rewritten, docs)
            reranked_docs = docs.copy()

            # Compress
            docs = self.compressor.compress(docs)
            context = build_context(docs)

            return context, rewritten, decomposed, queries, products, retrieved_docs, reranked_docs, docs

        # =========================
        # CASE 2: CÓ DECOMPOSE
        # =========================
        queries = []
        retrieved_docs = []
        reranked_docs = []
        final_docs = []

        for sub_q in decomposed:

            t0 = time.time()
            multi = multi_query_chain.invoke({"query": sub_q})
            sub_queries = list(dict.fromkeys([sub_q] + multi))
            queries.extend(sub_queries)
            logger.info(f"Sub-query: {sub_queries} ({(time.time()-t0):.2f}s)")

            t0 = time.time()
            products = detect_product(sub_q, self.products)
            if products == []:
                products = None
            logger.info(f"Detected products: {products} ({(time.time()-t0):.2f}s)")

            docs = self.retrieve(sub_queries, products)
            retrieved_docs.extend(docs)

        top_k = len(decomposed)*8

        reranked_docs = self.rerank(" ".join(decomposed), retrieved_docs, top_k=top_k)

        final_docs = self.compressor.compress(reranked_docs, max_docs= len(decomposed) * 5)

        context = build_context(final_docs)

        return context, rewritten, decomposed, queries, products, retrieved_docs, reranked_docs, final_docs

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
            logger.info(f"\nNEW QUERY: {query}")

            intent = detect_intent(query)
            trace["intent"] = intent

            logger.info(f"Intent: {intent}")

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

            # RUN PIPELINE
            context, rewritten, decomposed, queries, products, retrieved_docs, reranked_docs, docs = self.pipeline(query, history)

            trace["rewritten"] = rewritten
            trace["decomposed"] = decomposed
            trace["queries"] = queries
            trace["products"] = products
            trace["retrieved_docs"] = [d["doc_id"] for d in retrieved_docs]
            trace["reranked_docs"] = [d["doc_id"] for d in reranked_docs]
            trace["final_docs"] = [d["doc_id"] for d in docs]

            logger.info(f"Retrieved: {len(retrieved_docs)} | Reranked: {len(reranked_docs)} | Final: {len(docs)}")

            # Generate
            stream = generator_chain.stream({
                "context": context,
                "question": rewritten
            })

            for chunk in stream:
                if chunk.content:
                    full_response += chunk.content
                    yield chunk.content

            trace["response"] = full_response
            trace["latency_ms"] = int((time.time() - start_time) * 1000)

            logger.info(f"Total latency: {trace['latency_ms']} ms")

            save_rag_log(trace)

        except Exception as e:
            logger.exception("Pipeline error")
            trace["error"] = str(e)
            save_rag_log(trace)
            raise