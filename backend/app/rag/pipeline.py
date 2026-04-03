from typing import AsyncGenerator
import asyncio
import threading
import time
import uuid

from starlette.concurrency import run_in_threadpool

from app.rag.chains.rewrite_chain import rewrite_chain
from app.rag.chains.generator_chain import generator_chain
from app.rag.chains.generator_chain import chat_generator_chain
from app.rag.chains.decompose_chain import decompose_chain
from app.rag.chains.clarify_chain import (
    is_ambiguous_by_rule,
    extract_products_chain,
    build_clarification_message
)

from app.rag.cache.redis_cache import RedisCache
from app.rag.cache.semantic_cache import SemanticCache

from app.rag.retrieval.qdrant_retriever import QdrantRetriever
from app.rag.retrieval.reranker import Reranker
from app.rag.retrieval.compression import ContextCompressor

from app.rag.routers.intent_router import detect_intent

from app.rag.utils.context_builder import build_context
import re

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
        # FIX: share retriever → dùng chung connection pool, tránh cold TCP
        self.semantic_cache = SemanticCache(retriever=self.retriever)

        self.retrieve_top_k = 15
        self.final_top_k = 5

    # -------------------------
    # PREPROCESSING
    # -------------------------
    def _preprocess_query(self, query: str) -> str:
        """
        Strip bullet characters and normalize whitespace.
        Handles cases where user copies bot bullet suggestions like:
        "• Kinh doanh tai loc" or "* Vay tin chap"
        """
        query = re.sub(r'[•\*\-]\s*', ' ', query)
        query = re.sub(r'\s+', ' ', query).strip()
        return query

    def _should_decompose_rule(self, query: str) -> bool:
        query = query.lower()
        keywords = [
            " và ",
            " hoặc ",
            "những",
            "các",
            "/",   # FIX: dấu phẩy bị thiếu ở đây ở bản gốc, khiến "/" và "," bị nối thành "/,"
            ",",
        ]
        return any(k in query for k in keywords)

    # -------------------------
    # SAFE WRAPPERS
    # -------------------------
    async def _call_in_thread(self, fn, *args, **kwargs):
        """Chỉ dùng cho các hàm sync thực sự: detect_intent, compressor, save_rag_log."""
        return await run_in_threadpool(fn, *args, **kwargs)

    async def _save_log_safe(self, trace: dict):
        try:
            await run_in_threadpool(save_rag_log, trace)
        except Exception:
            logger.exception("Failed to save rag log")

    # -------------------------
    # LangChain chain calls — dùng .ainvoke() thay vì run_in_threadpool
    # -------------------------
    async def _invoke_rewrite(self, query: str, history) -> str:
        t0 = time.time()
        result = await rewrite_chain.ainvoke({"query": query, "history": history})
        logger.info(f"Rewrite: {result} ({(time.time() - t0):.2f}s)")
        return result

    async def _invoke_decompose(self, query: str) -> list:
        t0 = time.time()
        result = await decompose_chain.ainvoke({"query": query})
        logger.info(f"Decomposed: {result} ({(time.time() - t0):.2f}s)")
        return result

    # -------------------------
    # CLARIFY CHECK (Hybrid: rule + LLM extract)
    # -------------------------
    # Signature của clarification message — dùng để nhận biết bot vừa hỏi lại
    CLARIFY_SIGNATURE = "Bạn muốn tìm hiểu về sản phẩm nào"

    def _last_bot_was_clarification(self, history) -> bool:
        """Trả về True nếu bot vừa hỏi clarification ở turn trước.
        Dùng để tránh re-trigger clarify khi user đang TRẢ LỜI câu hỏi đó."""
        if not history:
            return False
        last_bot = next(
            (h for h in reversed(history) if h.get("role") == "assistant"),
            None
        )
        return last_bot is not None and self.CLARIFY_SIGNATURE in last_bot.get("content", "")

    async def _invoke_clarify(self, query: str, history) -> dict:
        """
        Hybrid clarification check:
        - Layer 0 (Guard): nếu bot vừa hỏi clarification, user đang trả lời → bỏ qua
        - Layer 1 (Rule): detect if query is ambiguous — fast, no token cost
        - Layer 2 (LLM): only if ambiguous, extract specific products from history
        """
        t0 = time.time()

        # LAYER 0: user đang trả lời câu hỏi clarify trước đó → không hỏi lại
        if self._last_bot_was_clarification(history):
            logger.info(f"Clarify check: skipped — user answering previous clarification ({(time.time() - t0):.4f}s)")
            return {"needs_clarification": False, "mentioned_products": []}

        ambiguous = is_ambiguous_by_rule(query, history)

        if not ambiguous:
            logger.info(f"Clarify check: not ambiguous by rule ({(time.time() - t0):.4f}s)")
            return {"needs_clarification": False, "mentioned_products": []}

        history_text = ""
        if history:
            lines = []
            for h in history[-5:]:
                role = "Nguoi dung" if h["role"] == "user" else "Tro ly"
                lines.append(f"{role}: {h['content']}")
            history_text = "\n".join(lines)

        try:
            result = await extract_products_chain.ainvoke({"history": history_text})
            products = result.get("products", [])
            # FIX: dedup — giữ thứ tự, loại bỏ tên sản phẩm trùng lặp
            products = list(dict.fromkeys(products))
            needs_clarification = len(products) >= 2
            logger.info(
                f"Clarify check: ambiguous=True, products={products}, "
                f"needs_clarification={needs_clarification} ({(time.time() - t0):.2f}s)"
            )
            return {"needs_clarification": needs_clarification, "mentioned_products": products}
        except Exception:
            logger.exception("Extract products chain failed, skipping clarification")
            return {"needs_clarification": False, "mentioned_products": []}

    async def _detect_intent(self, query: str) -> str:
        t0 = time.time()
        result = await self._call_in_thread(detect_intent, query)
        logger.info(f"Intent: {result} ({(time.time() - t0):.2f}s)")
        return result

    # -------------------------
    # RETRIEVE / RERANK / COMPRESS — giờ đã native async, gọi trực tiếp
    # -------------------------
    async def _retrieve_one(self, query: str) -> list:
        return await self.retriever.search(query, self.retrieve_top_k)

    async def retrieve(self, queries: list) -> list:
        logger.info(f"Retrieving {len(queries)} queries...")
        t0 = time.time()

        all_results = await asyncio.gather(
            *[self._retrieve_one(q) for q in queries],
            return_exceptions=True
        )

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

    async def rerank(self, query: str, docs: list, top_k: int = None) -> list:
        if not docs:
            return docs

        docs = docs[:30]
        k = top_k or self.final_top_k

        logger.info(f"Reranking {len(docs)} docs...")
        t0 = time.time()

        results = await self.reranker.rerank(query, docs, k)

        logger.info(f"Reranked to {len(results)} docs in {(time.time() - t0):.2f}s")
        return results

    async def compress(self, docs: list, max_docs: int = None) -> list:
        t0 = time.time()
        # ContextCompressor chưa có async — giữ threadpool
        if max_docs is not None:
            results = await self._call_in_thread(self.compressor.compress, docs, max_docs=max_docs)
        else:
            results = await self._call_in_thread(self.compressor.compress, docs)
        logger.info(f"Compressed to {len(results)} docs in {(time.time() - t0):.2f}s")
        return results

    async def build_context_async(self, docs: list) -> str:
        t0 = time.time()
        # build_context là string ops thuần — gọi trực tiếp không cần thread
        context = build_context(docs)
        logger.info(f"Context built in {(time.time() - t0):.2f}s")
        return context

    # -------------------------
    # STREAMING — fix asyncio.run() → run_coroutine_threadsafe
    # -------------------------
    async def _stream_generator(self, payload) -> AsyncGenerator[str, None]:
        async for chunk in generator_chain.astream(payload):
            content = getattr(chunk, "content", None)
            if content:
                yield content

    async def _stream_chat(self, query: str) -> AsyncGenerator[str, None]:
        async for chunk in chat_generator_chain.astream({"question": query}):
            content = getattr(chunk, "content", None)
            if content:
                yield content

    # -------------------------
    # PIPELINE (public — legacy, gọi từ non-stream context)
    # -------------------------
    async def pipeline(self, query: str, history):
        """Simplified: tái dùng _pipeline_from_rewritten, tránh duplicate logic."""
        rewritten = await self._invoke_rewrite(query, history)
        return await self._pipeline_from_rewritten(rewritten, history)

    # -------------------------
    # PIPELINE (from rewritten query — skip rewrite step)
    # -------------------------
    async def _pipeline_from_rewritten(
        self, rewritten: str, history,
        query_vector: list = None,
        decompose_task=None
    ):
        should_decompose = self._should_decompose_rule(rewritten)

        if should_decompose:
            if decompose_task is not None:
                # Task đã chạy ngầm từ Bước 2 — chỉ await kết quả, không gọi LLM lại
                decomposed = await decompose_task
            else:
                decomposed = await self._invoke_decompose(rewritten)
        else:
            if decompose_task is not None:
                decompose_task.cancel()
            decomposed = [rewritten]

        if not isinstance(decomposed, list):
            decomposed = [rewritten]

        # CASE 1: NO DECOMPOSE
        if len(decomposed) <= 1:
            queries = [rewritten]
            # Dùng lại query_vector đã embed ở stream() nếu có — tránh gọi OpenAI lần 2
            if query_vector is not None:
                docs = await self.retriever.search_with_vector(query_vector, self.retrieve_top_k)
                docs = docs if isinstance(docs, list) else []
            else:
                docs = await self.retrieve(queries)
            retrieved_docs = docs.copy()
            docs = await self.rerank(rewritten, docs)
            reranked_docs = docs.copy()
            docs = await self.compress(docs)
            context = await self.build_context_async(docs)

            return (context, rewritten, decomposed, queries, retrieved_docs, reranked_docs, docs)

        # CASE 2: WITH DECOMPOSE
        # Mỗi sub_query: check cache → nếu miss mới retrieve → rerank top5 → build_context
        # Cache theo từng sub_query, không cache theo rewritten

        async def process_subquery(sub_q: str) -> dict:
            """
            Pipeline cho 1 sub_query:
            1. Check Redis cache
            2. Check Semantic cache (nếu redis miss)
            3. Retrieve → rerank top5 → build_context (nếu cả 2 đều miss)
            4. Lưu cache fire-and-forget
            """
            # --- Redis check ---
            sub_cached = await self.redis_cache.get(sub_q)
            if sub_cached:
                sub_context = sub_cached.get("context") or sub_cached.get("response") or sub_cached
                logger.info(f"[Decompose] Redis hit: {sub_q[:50]}")
                return {
                    "sub_q": sub_q,
                    "context": sub_context,
                    "retrieved_docs": [],
                    "reranked_docs": [],
                    "final_docs": [],
                    "cache_hit": "redis",
                }

            # --- Semantic cache check ---
            sub_vector = await self.retriever.embed(sub_q)
            sub_cached_context = await self.semantic_cache.search_with_vector(sub_vector)
            if sub_cached_context:
                logger.info(f"[Decompose] Semantic hit: {sub_q[:50]}")
                asyncio.create_task(
                    self.redis_cache.set(sub_q, {"context": sub_cached_context})
                )
                return {
                    "sub_q": sub_q,
                    "context": sub_cached_context,
                    "retrieved_docs": [],
                    "reranked_docs": [],
                    "final_docs": [],
                    "cache_hit": "semantic",
                }

            # --- Cache miss: full retrieval pipeline ---
            docs = await self.retriever.search_with_vector(sub_vector, self.retrieve_top_k)
            retrieved = docs.copy()

            reranked = await self.rerank(sub_q, docs, top_k=self.final_top_k)
            final = await self.compress(reranked)
            sub_context = await self.build_context_async(final)

            # Lưu cache fire-and-forget — dùng sub_vector đã tính, không re-embed
            asyncio.create_task(self.redis_cache.set(sub_q, {"context": sub_context}))
            asyncio.create_task(self.semantic_cache.add_with_vector(sub_q, sub_context, sub_vector))

            logger.info(f"[Decompose] Cache miss, retrieved {len(retrieved)} docs: {sub_q[:50]}")
            return {
                "sub_q": sub_q,
                "context": sub_context,
                "retrieved_docs": retrieved,
                "reranked_docs": reranked,
                "final_docs": final,
                "cache_hit": None,
            }

        # Chạy tất cả sub_queries song song
        sub_results = await asyncio.gather(
            *(process_subquery(sub_q) for sub_q in decomposed)
        )

        # Gộp kết quả
        queries = [r["sub_q"] for r in sub_results]
        retrieved_docs = []
        reranked_docs = []
        final_docs = []
        seen = set()
        for r in sub_results:
            for d in r["retrieved_docs"]:
                if d["doc_id"] not in seen:
                    seen.add(d["doc_id"])
                    retrieved_docs.append(d)
            reranked_docs.extend(r["reranked_docs"])
            final_docs.extend(r["final_docs"])

        # Merge context từ tất cả sub_queries (cache hit hoặc fresh)
        context_parts = [r["context"] for r in sub_results if r["context"]]
        context = "\n\n---\n\n".join(context_parts)

        cache_hits = [r["cache_hit"] for r in sub_results if r["cache_hit"]]
        if cache_hits:
            logger.info(f"[Decompose] Cache hits: {cache_hits}")

        return (context, rewritten, decomposed, queries, retrieved_docs, reranked_docs, final_docs)

    # -------------------------
    # MAIN STREAM ENTRY POINT
    # -------------------------
    async def stream(
        self,
        query: str,
        history=None,
        session_id: str = None
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
            query = self._preprocess_query(query)
            logger.info(f"NEW QUERY: {query}")

            # -------------------------
            # BƯỚC 1: Rewrite + Clarify SONG SONG
            # Rewrite trước để intent dùng câu đã chuẩn hóa — chính xác và nhanh hơn
            # Clarify dùng query GỐC (trước rewrite) nên chạy song song được
            # -------------------------
            rewritten, clarify_result = await asyncio.gather(
                self._invoke_rewrite(query, history),
                self._invoke_clarify(query, history)
            )

            # -------------------------
            # BƯỚC 2: Intent + Redis + Embed SONG SONG (3 tasks độc lập)
            # - Intent dùng rewritten — chính xác hơn query gốc
            # - Redis check không phụ thuộc intent
            # - Embed(rewritten) bắt đầu sớm: dùng lại cho semantic cache và retrieve
            # -------------------------
            # Nếu cần decompose, bắt đầu ngay sau khi có rewritten (chạy ngầm)
            # Đến lúc cần sẽ await — thường đã xong hoặc gần xong
            should_decompose_early = self._should_decompose_rule(rewritten)
            decompose_task = (
                asyncio.create_task(self._invoke_decompose(rewritten))
                if should_decompose_early else None
            )

            intent, cached, query_vector = await asyncio.gather(
                self._detect_intent(rewritten),
                self.redis_cache.get(rewritten),
                self.retriever.embed(rewritten),   # embed sớm — không còn sequential
            )
            trace["intent"] = intent

            if intent == "CHAT":
                if decompose_task:
                    decompose_task.cancel()
                async for token in self._stream_chat(rewritten):
                    yield token
                return

            if intent == "OUT_OF_SCOPE":
                if decompose_task:
                    decompose_task.cancel()
                msg = (
                    "Xin lỗi, tôi chỉ hỗ trợ thông tin ngân hàng Vietcombank. "
                    "Bạn có thể hỏi về sản phẩm, phí, lãi suất hoặc dịch vụ của Vietcombank."
                )
                yield msg
                return

            # -------------------------
            # -------------------------
            # BƯỚC 3: Clarify TRƯỚC cache (cache không lưu trạng thái hội thoại)
            # -------------------------
            if clarify_result.get("needs_clarification"):
                if decompose_task:
                    decompose_task.cancel()
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

            # Redis result đã có từ gather ở Bước 2 — dùng lại, không gọi lại
            if cached:
                if decompose_task:
                    decompose_task.cancel()
                retrieval_latency_ms = int((time.time() - start_time) * 1000)
                trace["retrieval_latency_ms"] = retrieval_latency_ms
                logger.info(f"Redis cache hit | Retrieval latency: {retrieval_latency_ms} ms")
                context = cached.get("context") or cached.get("response") or cached

                async for token in self._stream_generator({
                    "context": context,
                    "history": history,
                    "question": rewritten
                }):
                    yield token

                trace["latency_ms"] = int((time.time() - start_time) * 1000)
                logger.info(f"Total latency: {trace['latency_ms']} ms")
                return

            # query_vector đã có từ Bước 2 (không embed lại)
            cached_context = await self.semantic_cache.search_with_vector(query_vector)

            if cached_context:
                if decompose_task:
                    decompose_task.cancel()
                retrieval_latency_ms = int((time.time() - start_time) * 1000)
                trace["retrieval_latency_ms"] = retrieval_latency_ms
                logger.info(f"Semantic cache hit | Retrieval latency: {retrieval_latency_ms} ms")

                asyncio.create_task(self.redis_cache.set(rewritten, {"context": cached_context}))

                async for token in self._stream_generator({
                    "context": cached_context,
                    "history": history,
                    "question": rewritten
                }):
                    yield token

                trace["latency_ms"] = int((time.time() - start_time) * 1000)
                logger.info(f"Total latency: {trace['latency_ms']} ms")
                return

            # -------------------------
            # NORMAL RAG PIPELINE — truyền query_vector và decompose_task đang chạy ngầm
            # -------------------------
            result = await self._pipeline_from_rewritten(
                rewritten, history,
                query_vector=query_vector,
                decompose_task=decompose_task
            )

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

            retrieval_latency_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"Retrieved: {len(retrieved_docs)} | "
                f"Reranked: {len(reranked_docs)} | "
                f"Final: {len(docs)} | "
                f"Retrieval latency: {retrieval_latency_ms} ms"
            )
            trace["retrieval_latency_ms"] = retrieval_latency_ms

            async for token in self._stream_generator({
                "context": context,
                "history": history,
                "question": rewritten
            }):
                full_response += token
                yield token

            trace["response"] = full_response

            # Lưu cache:
            # - DECOMPOSE: cache đã được lưu theo từng sub_query bên trong _pipeline_from_rewritten
            # - NO DECOMPOSE: lưu theo rewritten query, dùng query_vector đã có — không re-embed
            if len(decomposed) <= 1:
                asyncio.create_task(self.redis_cache.set(rewritten, {"context": context}))
                asyncio.create_task(self.semantic_cache.add_with_vector(rewritten, context, query_vector))
            else:
                logger.info(f"[Decompose] Cache lưu theo {len(decomposed)} sub_queries, bỏ qua rewritten cache")

            trace["latency_ms"] = int((time.time() - start_time) * 1000)
            logger.info(f"Total latency: {trace['latency_ms']} ms")

            asyncio.create_task(self._save_log_safe(trace))

        except Exception as e:
            logger.exception("Pipeline error")
            trace["error"] = str(e)
            asyncio.create_task(self._save_log_safe(trace))
            raise