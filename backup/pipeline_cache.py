from typing import Generator
import time
import uuid
import os
import hashlib
import json
import redis

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

# =========================
# Redis helpers
# =========================

def make_cache_key(prefix, data):
    raw = prefix + json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(raw.encode()).hexdigest()


def get_cache(r, key):
    try:
        val = r.get(key)
        if val:
            return json.loads(val)
    except Exception as e:
        logger.warning(f"Redis get error: {e}")
    return None


def set_cache(r, key, value, ttl):
    try:
        r.setex(key, ttl, json.dumps(value, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"Redis set error: {e}")


class RAGPipeline:

    def __init__(self):

        logger.info("Initializing RAGPipeline")

        # =========================
        # Redis init
        # =========================
        redis_url = os.getenv("REDIS_URL")

        if redis_url:
            self.redis = redis.from_url(redis_url, decode_responses=True)
            logger.info("Redis connected")
        else:
            self.redis = None
            logger.warning("Redis NOT configured, fallback no-cache")

        self.cache_ttl = 600  # 10 minutes

        # =========================
        # Core components
        # =========================
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

        products = set()
        for d in data:
            p = d.get("product_name")
            if p:
                products.add(p)

        return list(products)

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
            # Rewrite (CACHE)
            # -------------------------
            rewrite_key = make_cache_key("rewrite", {
                "query": query,
                "history": history
            })

            rewritten = get_cache(self.redis, rewrite_key) if self.redis else None

            if not rewritten:
                rewritten = rewrite_chain.invoke({
                    "query": query,
                    "history": history
                })
                if self.redis:
                    set_cache(self.redis, rewrite_key, rewritten, self.cache_ttl)

            trace["rewritten"] = rewritten

            # -------------------------
            # Product
            # -------------------------
            products = detect_product(rewritten, self.products)
            trace["products"] = products

            # -------------------------
            # Multi query
            # -------------------------
            multi_queries = multi_query_chain.invoke({
                "query": rewritten
            })

            queries = list(dict.fromkeys([rewritten] + multi_queries))
            trace["queries"] = queries

            # -------------------------
            # Retrieval (CACHE)
            # -------------------------
            retrieval_key = make_cache_key("retrieval", {
                "queries": queries
            })

            docs = get_cache(self.redis, retrieval_key) if self.redis else None

            if not docs:
                docs = self.retrieve(queries)
                if self.redis:
                    set_cache(self.redis, retrieval_key, docs, self.cache_ttl)

            trace["retrieved_docs"] = [d["doc_id"] for d in docs]

            # -------------------------
            # Product filter
            # -------------------------
            docs = self.filter_products(docs, products)

            # -------------------------
            # Rerank (CACHE)
            # -------------------------
            rerank_key = make_cache_key("rerank", {
                "query": rewritten,
                "doc_ids": [d["doc_id"] for d in docs]
            })

            cached_rerank = get_cache(self.redis, rerank_key) if self.redis else None

            if cached_rerank:
                docs = cached_rerank
            else:
                docs = self.rerank(rewritten, docs)
                if self.redis:
                    set_cache(self.redis, rerank_key, docs, self.cache_ttl)

            trace["reranked_docs"] = [d["doc_id"] for d in docs]

            # -------------------------
            # Compress
            # -------------------------
            docs = self.compressor.compress(docs)
            trace["final_docs"] = [d["doc_id"] for d in docs]

            # -------------------------
            # Context
            # -------------------------
            context = build_context(docs)

            # -------------------------
            # Generate
            # -------------------------
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

            save_rag_log(trace)

        except Exception as e:
            trace["error"] = str(e)
            save_rag_log(trace)
            raise
