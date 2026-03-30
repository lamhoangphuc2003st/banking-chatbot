from typing import AsyncGenerator
import asyncio
import json
import time
import uuid

from starlette.concurrency import run_in_threadpool

from app.rag.chains.rewrite_chain import rewrite_chain
from app.rag.chains.generator_chain import generator_chain
from app.rag.chains.generator_chain import chat_generator_chain
from app.rag.chains.decompose_chain import decompose_chain
from app.rag.chains.clarify_chain import (is_ambiguous_by_rule, extract_products_chain, build_clarification_message)

from app.rag.cache.redis_cache import RedisCache
from app.rag.cache.semantic_cache import SemanticCache

from app.rag.retrieval.qdrant_retriever import QdrantRetriever
from app.rag.retrieval.reranker import Reranker
from app.rag.retrieval.compression import ContextCompressor

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

        self.redis_cache = RedisCache()
        self.semantic_cache = SemanticCache()

        self.retrieve_top_k = 15
        self.final_top_k = 5

    def _should_decompose_rule(self, query):
        query = query.lower()

        keywords = [
            " và ",
            " hoặc ",
            "những",
            "các",
            "/"
            ","
        ]

        return any(k in query for k in keywords)

    # -------------------------
    # PREPROCESSING
    # -------------------------
    def _preprocess_query(self, query: str) -> str:
        """
        Strip bullet characters and normalize whitespace.
        Handles cases where user copies bot bullet suggestions like:
        "• Kinh doanh tai loc" or "* Vay tin chap"
        """
        import re
        # Remove bullet characters at the start of each segment
        query = re.sub(r'[•\*\-]\s*', ' ', query)
        # Collapse multiple spaces/newlines
        query = re.sub(r'\s+', ' ', query).strip()
        return query

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

    # -------------------------
    # CLARIFY CHECK (Hybrid: rule + LLM extract)
    # -------------------------
    async def _invoke_clarify(self, query, history):
        """
        Hybrid clarification check:
        - Layer 1 (Rule): detect if query is ambiguous — fast, no token cost
        - Layer 2 (LLM): only if ambiguous, extract specific products from history
        Returns dict: {"needs_clarification": bool, "mentioned_products": list[str]}
        """
        t0 = time.time()

        # LAYER 1: Rule-based ambiguity detection (no LLM, instant)
        ambiguous = is_ambiguous_by_rule(query, history)

        if not ambiguous:
            logger.info(f"Clarify check: not ambiguous by rule ({(time.time() - t0):.4f}s)")
            return {"needs_clarification": False, "mentioned_products": []}

        # LAYER 2: LLM extracts products from history (only reached if ambiguous)
        history_text = ""
        if history:
            lines = []
            for h in history[-10:]:
                role = "Nguoi dung" if h["role"] == "user" else "Tro ly"
                lines.append(f"{role}: {h['content']}")
            history_text = "\n".join(lines)

        try:
            result = await self._call_in_thread(
                extract_products_chain.invoke,
                {"history": history_text}
            )
            products = result.get("products", [])
            # Only ask for clarification if there are ≥2 specific products to suggest
            needs_clarification = len(products) >= 2
            logger.info(
                f"Clarify check: ambiguous=True, products={products}, "
                f"needs_clarification={needs_clarification} ({(time.time() - t0):.2f}s)"
            )
            return {"needs_clarification": needs_clarification, "mentioned_products": products}
        except Exception:
            logger.exception("Extract products chain failed, skipping clarification")
            return {"needs_clarification": False, "mentioned_products": []}

    async def _detect_intent(self, query):
        t0 = time.time()
        result = await self._call_in_thread(detect_intent, query)
        logger.info(f"Intent: {result} ({(time.time() - t0):.2f}s)")
        return result

    async def _retrieve_one(self, query):
        return await self._call_in_thread(
            self.retriever.search,
            query,
            self.retrieve_top_k,
        )

    async def retrieve(self, queries):
        logger.info(f"Retrieving {len(queries)} queries...")
        t0 = time.time()

        tasks = [self._retrieve_one(q) for q in queries]
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
        queue = asyncio.Queue()

        def worker():
            try:
                for chunk in generator_chain.stream(payload):
                    content = getattr(chunk, "content", None)
                    if content:
                        asyncio.run(queue.put(content))
            finally:
                asyncio.run(queue.put(None))

        import threading
        threading.Thread(target=worker, daemon=True).start()

        while True:
            token = await queue.get()
            if token is None:
                break
            yield token

    async def _stream_chat(self, query) -> AsyncGenerator[str, None]:
        queue = asyncio.Queue()

        def worker():
            try:
                for chunk in chat_generator_chain.stream({
                    "question": query
                }):
                    content = getattr(chunk, "content", None)
                    if content:
                        asyncio.run(queue.put(content))
            finally:
                asyncio.run(queue.put(None))

        import threading
        threading.Thread(target=worker, daemon=True).start()

        while True:
            token = await queue.get()
            if token is None:
                break
            yield token

    # -------------------------
    # MAIN PIPELINE
    # -------------------------
    async def pipeline(self, query, history):
        # Rewrite
        rewritten = await self._invoke_rewrite(query, history)

        # Decide decompose
        should_decompose = self._should_decompose_rule(rewritten)

        if should_decompose:
            decomposed = await self._invoke_decompose(rewritten)
        else:
            decomposed = [rewritten]

        if not isinstance(decomposed, list):
            decomposed = [rewritten]

        # =========================
        # CASE 1: NO DECOMPOSE
        # =========================
        if len(decomposed) <= 1:

            queries = [rewritten]

            docs = await self.retrieve(queries)

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

            docs = await self.retrieve([sub_q])

            return {
                "sub_q": sub_q,
                "docs": docs,
            }

        # Chạy các sub-query song song
        results = await asyncio.gather(*(process_subquery(sub_q) for sub_q in decomposed))

        for item in results:
            queries.append(item["sub_q"])
            retrieved_docs.extend(item["docs"])

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
            # -------------------------
            # PREPROCESSING: strip bullet characters
            # Handles cases where user copies bot suggestions like "• Kinh doanh tai loc"
            # -------------------------
            query = self._preprocess_query(query)
            logger.info(f"NEW QUERY: {query}")

            intent = await self._detect_intent(query)
            trace["intent"] = intent

            if intent == "CHAT":
                async for token in self._stream_chat(query):
                    yield token
                return

            if intent == "OUT_OF_SCOPE":
                msg = (
                    "Xin lỗi, tôi chỉ hỗ trợ thông tin ngân hàng Vietcombank. "
                    "Bạn có thể hỏi về sản phẩm, phí, lãi suất hoặc dịch vụ của Vietcombank."
                )
                yield msg
                return
            
            # -------------------------
            # REWRITE + CLARIFY SONG SONG
            # clarify dùng query GỐC (trước rewrite) để tránh rewrite che mất sự mơ hồ
            # -------------------------
            rewritten = await self._invoke_rewrite(query, history)
     
            cached = self.redis_cache.get(rewritten)

            if cached:
                logger.info("Redis retrieval cache hit")

                context = cached.get("context")

                # backward compatibility
                if not context:
                    context = cached.get("response")

                if not context:
                    context = cached

                async for token in self._stream_generator({
                    "context": context,
                    "history": history,
                    "question": rewritten
                }):
                    yield token

                trace["latency_ms"] = int((time.time() - start_time) * 1000)

                logger.info(f"Total latency: {trace['latency_ms']} ms")

                return

            
            # semantic cache
            cached_context = self.semantic_cache.search(rewritten)

            if cached_context:
                logger.info("Semantic retrieval cache hit")

                self.redis_cache.set(
                    rewritten,
                    {"context": cached_context}
                )

                async for token in self._stream_generator({
                    "context": cached_context,
                    "history": history,
                    "question": rewritten
                }):
                    yield token

                trace["latency_ms"] = int((time.time() - start_time) * 1000)

                logger.info(f"Total latency: {trace['latency_ms']} ms")

                return
            
            
            clarify_result = await self._invoke_clarify(query, history)
            
            if clarify_result.get("needs_clarification"):
                mentioned_products = clarify_result.get("mentioned_products", [])
                clarification_msg = build_clarification_message(mentioned_products)

                logger.info(f"Clarification needed. Products suggested: {mentioned_products}")
                trace["clarification"] = True
                trace["mentioned_products"] = mentioned_products
                trace["response"] = clarification_msg
                trace["latency_ms"] = int((time.time() - start_time) * 1000)

                yield clarification_msg

                asyncio.create_task(self._save_log_safe(trace))
                return

            # -------------------------
            # NORMAL RAG PIPELINE
            # (rewritten đã có, truyền thẳng vào pipeline thay vì rewrite lại)
            # -------------------------
            result = await self._pipeline_from_rewritten(rewritten, history)

            (
                context,
                rewritten,
                decomposed,
                queries,
                retrieved_docs,
                reranked_docs,
                docs,
            ) = result

            trace["rewritten"] = rewritten
            trace["decomposed"] = decomposed
            trace["queries"] = queries
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
                "history": history,
                "question": rewritten
            }):
                full_response += token
                yield token

            trace["response"] = full_response
            trace["response"] = full_response

            # # save cache
            self.redis_cache.set(
                rewritten,
                {"context": context}
            )

            self.semantic_cache.add(
                rewritten,
                context
            )
                
            trace["latency_ms"] = int((time.time() - start_time) * 1000)

            logger.info(f"Total latency: {trace['latency_ms']} ms")

            asyncio.create_task(self._save_log_safe(trace))

        except Exception as e:
            logger.exception("Pipeline error")
            trace["error"] = str(e)
            asyncio.create_task(self._save_log_safe(trace))
            raise

    # -------------------------
    # PIPELINE (from rewritten query — skip rewrite step)
    # -------------------------
    async def _pipeline_from_rewritten(self, rewritten, history):
        """
        Same as pipeline() but accepts an already-rewritten query.
        Avoids calling rewrite_chain twice.
        """
        should_decompose = self._should_decompose_rule(rewritten)

        if should_decompose:
            decomposed = await self._invoke_decompose(rewritten)
        else:
            decomposed = [rewritten]

        if not isinstance(decomposed, list):
            decomposed = [rewritten]

        # CASE 1: NO DECOMPOSE
        if len(decomposed) <= 1:
            queries = [rewritten]
            docs = await self.retrieve(queries)
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
                retrieved_docs,
                reranked_docs,
                docs,
            )

        # CASE 2: WITH DECOMPOSE
        queries = []
        retrieved_docs = []

        async def process_subquery(sub_q):
            docs = await self.retrieve([sub_q])
            return {"sub_q": sub_q, "docs": docs}

        results = await asyncio.gather(*(process_subquery(sub_q) for sub_q in decomposed))

        for item in results:
            queries.append(item["sub_q"])
            retrieved_docs.extend(item["docs"])

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
            retrieved_docs,
            reranked_docs,
            final_docs,
        )