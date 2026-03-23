from typing import AsyncGenerator
import asyncio
import json
import time
import uuid

from starlette.concurrency import run_in_threadpool

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
        logger.info("Initializing RAGPipeline")

        self.retriever = QdrantRetriever()
        self.reranker = Reranker()
        self.compressor = ContextCompressor()

        self.retrieve_top_k = 15
        self.final_top_k = 5

        self.products = self.load_products()

    # -------------------------
    # INIT / STATIC DATA
    # -------------------------
    def load_products(self):
        with open("data/vietcombank_chunks.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        products = set()

        for d in data:
            name = d.get("metadata", {}).get("product_name")
            if name:
                name = " ".join(name.strip().split())
                products.add(name)

        products = sorted(list(products))

        logger.info(f"Loaded {len(products)} products")
        return products

    # -------------------------
    # SAFE WRAPPERS
    # -------------------------
    async def _call_in_thread(self, fn, *args, **kwargs):
        return await run_in_threadpool(fn, *args, **kwargs)

    async def _save_log_safe(self, trace: dict):
        try:
            await run_in_threadpool(save_rag_log, trace)
        except Exception:
            logger.exception("Failed to save rag log")

    async def _invoke_rewrite(self, query, history):
        t0 = time.time()
        result = await self._call_in_thread(
            rewrite_chain.invoke,
            {
                "query": query,
                "history": history
            }
        )
        logger.info(f"Rewrite: {result} ({(time.time() - t0):.2f}s)")
        return result

    async def _invoke_decompose(self, query):
        t0 = time.time()
        result = await self._call_in_thread(
            decompose_chain.invoke,
            {
                "query": query
            }
        )
        logger.info(f"Decomposed: {result} ({(time.time() - t0):.2f}s)")
        return result

    async def _invoke_multi_query(self, query):
        t0 = time.time()
        result = await self._call_in_thread(
            multi_query_chain.invoke,
            {
                "query": query
            }
        )
        logger.info(f"Multi-query for '{query}': {result} ({(time.time() - t0):.2f}s)")
        return result

    async def _detect_intent(self, query):
        t0 = time.time()
        result = await self._call_in_thread(detect_intent, query)
        logger.info(f"Intent: {result} ({(time.time() - t0):.2f}s)")
        return result

    async def _detect_product(self, query):
        t0 = time.time()
        result = await self._call_in_thread(detect_product, query, self.products)
        if result == []:
            result = None
        logger.info(f"Detected products for '{query}': {result} ({(time.time() - t0):.2f}s)")
        return result

    async def _retrieve_one(self, query, products):
        return await self._call_in_thread(
            self.retriever.search,
            query,
            self.retrieve_top_k,
            products
        )

    async def retrieve(self, queries, products):
        logger.info(f"Retrieving {len(queries)} queries...")
        t0 = time.time()

        tasks = [self._retrieve_one(q, products) for q in queries]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        docs = []
        seen = set()

        for i, results in enumerate(all_results):
            if isinstance(results, Exception):
                logger.exception(f"Retrieve failed for query: {queries[i]}")
                continue

            for d in results:
                doc_id = d["doc_id"]
                if doc_id not in seen:
                    seen.add(doc_id)
                    docs.append(d)

        logger.info(f"Retrieved {len(docs)} unique docs in {(time.time() - t0):.2f}s")
        return docs

    async def rerank(self, query, docs, top_k=None):
        if not docs:
            return docs

        docs = docs[:30]
        k = top_k or self.final_top_k

        logger.info(f"Reranking {len(docs)} docs...")
        t0 = time.time()

        results = await self._call_in_thread(
            self.reranker.rerank,
            query,
            docs,
            k
        )

        logger.info(f"Reranked to {len(results)} docs in {(time.time() - t0):.2f}s")
        return results

    async def compress(self, docs, max_docs=None):
        t0 = time.time()
        if max_docs is not None:
            results = await self._call_in_thread(
                self.compressor.compress,
                docs,
                max_docs=max_docs
            )
        else:
            results = await self._call_in_thread(
                self.compressor.compress,
                docs
            )
        logger.info(f"Compressed to {len(results)} docs in {(time.time() - t0):.2f}s")
        return results

    async def build_context_async(self, docs):
        t0 = time.time()
        context = await self._call_in_thread(build_context, docs)
        logger.info(f"Context built in {(time.time() - t0):.2f}s")
        return context

    async def _stream_generator(self, payload) -> AsyncGenerator[str, None]:
        iterator = await self._call_in_thread(generator_chain.stream, payload)
        def next_chunk(it):
            try:
                return next(it)
            except StopIteration:
                return None
        while True:
            chunk = await self._call_in_thread(next_chunk, iterator)
            if chunk is None:
                break
            content = getattr(chunk, "content", None)
            if content:
                yield content

    # -------------------------
    # MAIN PIPELINE
    # -------------------------
    async def pipeline(self, query, history):
        # Rewrite
        rewritten = await self._invoke_rewrite(query, history)

        # Decompose
        decomposed = await self._invoke_decompose(rewritten)

        if not isinstance(decomposed, list):
            decomposed = [rewritten]

        # =========================
        # CASE 1: NO DECOMPOSE
        # =========================
        if len(decomposed) <= 1:
            multi_queries = await self._invoke_multi_query(rewritten)
            queries = list(dict.fromkeys([rewritten] + multi_queries))

            products = await self._detect_product(rewritten)

            docs = await self.retrieve(queries, products)
            retrieved_docs = docs.copy()

            docs = await self.rerank(rewritten, docs)
            reranked_docs = docs.copy()

            docs = await self.compress(docs)
            context = await self.build_context_async(docs)

            return (
                context,
                rewritten,
                decomposed,
                queries,
                products,
                retrieved_docs,
                reranked_docs,
                docs,
            )

        # =========================
        # CASE 2: WITH DECOMPOSE
        # =========================
        queries = []
        retrieved_docs = []

        async def process_subquery(sub_q):
            multi = await self._invoke_multi_query(sub_q)
            sub_queries = list(dict.fromkeys([sub_q] + multi))

            products = await self._detect_product(sub_q)
            docs = await self.retrieve(sub_queries, products)

            return {
                "sub_q": sub_q,
                "sub_queries": sub_queries,
                "products": products,
                "docs": docs,
            }

        # Chạy các sub-query song song
        results = await asyncio.gather(*(process_subquery(sub_q) for sub_q in decomposed))

        all_products = []

        for item in results:
            queries.extend(item["sub_queries"])
            retrieved_docs.extend(item["docs"])
            if item["products"]:
                all_products.extend(item["products"])

        # dedupe products
        products = sorted(list(set(all_products))) if all_products else None

        # dedupe retrieved docs
        unique_docs = []
        seen = set()
        for d in retrieved_docs:
            doc_id = d["doc_id"]
            if doc_id not in seen:
                seen.add(doc_id)
                unique_docs.append(d)
        retrieved_docs = unique_docs

        top_k = len(decomposed) * 8

        reranked_docs = await self.rerank(" ".join(decomposed), retrieved_docs, top_k=top_k)
        final_docs = await self.compress(reranked_docs, max_docs=len(decomposed) * 5)
        context = await self.build_context_async(final_docs)

        return (
            context,
            rewritten,
            decomposed,
            queries,
            products,
            retrieved_docs,
            reranked_docs,
            final_docs,
        )

    # -------------------------
    # STREAM
    # -------------------------
    async def stream(
        self,
        query,
        history=None,
        session_id=None
    ) -> AsyncGenerator[str, None]:
        start_time = time.time()
        session_id = session_id or str(uuid.uuid4())

        trace = {
            "session_id": session_id,
            "query": query,
            "history": history
        }

        full_response = ""

        try:
            logger.info(f"NEW QUERY: {query}")

            intent = await self._detect_intent(query)
            trace["intent"] = intent

            if intent == "CHAT":
                async for token in self._stream_generator({
                    "context": "",
                    "question": query
                }):
                    full_response += token
                    yield token

                trace["response"] = full_response
                trace["latency_ms"] = int((time.time() - start_time) * 1000)

                asyncio.create_task(self._save_log_safe(trace))
                return

            (
                context,
                rewritten,
                decomposed,
                queries,
                products,
                retrieved_docs,
                reranked_docs,
                docs,
            ) = await self.pipeline(query, history)

            trace["rewritten"] = rewritten
            trace["decomposed"] = decomposed
            trace["queries"] = queries
            trace["products"] = products
            trace["retrieved_docs"] = [d["doc_id"] for d in retrieved_docs]
            trace["reranked_docs"] = [d["doc_id"] for d in reranked_docs]
            trace["final_docs"] = [d["doc_id"] for d in docs]

            logger.info(
                f"Retrieved: {len(retrieved_docs)} | "
                f"Reranked: {len(reranked_docs)} | "
                f"Final: {len(docs)}"
            )

            async for token in self._stream_generator({
                "context": context,
                "question": rewritten
            }):
                full_response += token
                yield token

            trace["response"] = full_response
            trace["latency_ms"] = int((time.time() - start_time) * 1000)

            logger.info(f"Total latency: {trace['latency_ms']} ms")

            asyncio.create_task(self._save_log_safe(trace))

        except Exception as e:
            logger.exception("Pipeline error")
            trace["error"] = str(e)
            asyncio.create_task(self._save_log_safe(trace))
            raise
