from typing import Generator
import time
import uuid
import asyncio

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
        logger.info("Initializing Async RAGPipeline")

        self.retriever = HybridRetriever(
            "data/vietcombank_chunks.json",
            "data/faiss_index.bin"
        )

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

        products = list({d.get("product_name") for d in data if d.get("product_name")})
        logger.info(f"Loaded {len(products)} products")
        return products

    # -------------------------
    async def retrieve_async(self, queries):

        logger.info(f"Retrieving {len(queries)} queries...")
        t0 = time.time()

        loop = asyncio.get_event_loop()

        tasks = [
            loop.run_in_executor(None, self.retriever.search, q)
            for q in queries
        ]

        results_list = await asyncio.gather(*tasks)

        docs = []
        seen = set()

        for results in results_list:
            for d in results:
                doc_id = d["doc_id"]
                if doc_id not in seen:
                    seen.add(doc_id)
                    docs.append(d)

        logger.info(f"Retrieved {len(docs)} unique docs in {(time.time()-t0):.2f}s")
        return docs

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

        logger.info(f"Product filter: {len(filtered)}/{len(docs)} docs kept")
        return filtered if filtered else docs

    # -------------------------
    def rerank(self, query, docs):

        if not docs:
            return docs

        docs = docs[:30]

        logger.info(f"Reranking {len(docs)} docs...")
        t0 = time.time()

        results = self.reranker.rerank(query, docs, k=self.final_top_k)

        logger.info(f"Reranked to {len(results)} docs in {(time.time()-t0):.2f}s")
        return results

    # -------------------------
    async def async_pipeline(self, query, history):

        loop = asyncio.get_event_loop()

        # Rewrite
        t0 = time.time()
        rewritten = await loop.run_in_executor(
            None,
            lambda: rewrite_chain.invoke({
                "query": query,
                "history": history
            })
        )
        logger.info(f"Rewrite: {rewritten} ({(time.time()-t0):.2f}s)")

        # Multi-query
        t0 = time.time()
        multi_queries = await loop.run_in_executor(
            None,
            lambda: multi_query_chain.invoke({"query": rewritten})
        )
        logger.info(f"Multi-query: {multi_queries} ({(time.time()-t0):.2f}s)")

        queries = list(dict.fromkeys([rewritten] + multi_queries))

        # Retrieve
        docs = await self.retrieve_async(queries)
        retrieved_docs = docs.copy()

        # Product filter
        products = detect_product(rewritten, self.products)
        docs = self.filter_products(docs, products)

        # Rerank
        docs = await loop.run_in_executor(
            None,
            lambda: self.rerank(rewritten, docs)
        )
        reranked_docs = docs.copy()

        # Compress
        t0 = time.time()
        docs = self.compressor.compress(docs)
        logger.info(f"Compressed to {len(docs)} docs ({(time.time()-t0):.2f}s)")

        context = build_context(docs)

        return context, rewritten, queries, products, retrieved_docs, reranked_docs, docs

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
            context, rewritten, queries, products, retrieved_docs, reranked_docs, docs = asyncio.run(
                self.async_pipeline(query, history)
            )

            trace["rewritten"] = rewritten
            trace["queries"] = queries
            trace["products"] = products
            trace["retrieved_docs"] = [d["doc_id"] for d in retrieved_docs]
            trace["reranked_docs"] = [d["doc_id"] for d in reranked_docs]
            trace["final_docs"] = [d["doc_id"] for d in docs]

            logger.info(f"Retrieved: {len(retrieved_docs)} | Reranked: {len(reranked_docs)} | Final: {len(docs)}")

            # Generate
            stream = generator_chain.stream({
                "context": context,
                "question": query
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