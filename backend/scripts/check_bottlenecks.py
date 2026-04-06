# scripts/check_bottlenecks.py
"""
Chạy khi đang load test để xác định bottleneck.

    cd backend
    python scripts/check_bottlenecks.py
"""
import asyncio
import sys
import time
from pathlib import Path

# Load env + project path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from dotenv import load_dotenv
    for p in [Path(__file__).resolve().parent.parent, Path(__file__).resolve().parent.parent.parent]:
        if (p / ".env").exists():
            load_dotenv(p / ".env")
            break
except ImportError:
    pass

async def probe_openai():
    """Đo latency thực tế đến OpenAI"""
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model="gpt-4o-mini")
    t0 = time.time()
    await llm.ainvoke("ping")
    return time.time() - t0

async def probe_qdrant():
    """Đo latency đến Qdrant"""
    from app.rag.retrieval.qdrant_retriever import QdrantRetriever
    r = QdrantRetriever()
    t0 = time.time()
    await r.client.get_collections()
    return time.time() - t0

async def probe_redis():
    """Đo latency đến Redis"""
    from app.rag.cache.redis_cache import RedisCache
    c = RedisCache()
    t0 = time.time()
    await c.get("__probe__")
    return time.time() - t0

async def probe_cohere():
    """Đo latency đến Cohere"""
    import cohere, os, time
    client = cohere.AsyncClient(os.getenv("COHERE_API_KEY"))
    docs = ["test document " * 10] * 5
    t0 = time.time()
    await client.rerank(model="rerank-v3.5", query="test", documents=docs, top_n=3)
    return time.time() - t0

async def main():
    print("Probing external services...")
    results = await asyncio.gather(
        probe_openai(),
        probe_qdrant(),
        probe_redis(),
        probe_cohere(),
        return_exceptions=True
    )
    services = ["OpenAI", "Qdrant", "Redis", "Cohere"]
    for service, result in zip(services, results):
        if isinstance(result, Exception):
            print(f"  {service:<10}: ERROR — {result}")
        else:
            status = "🔴 SLOW" if result > 2 else "🟡 OK" if result > 0.5 else "✅ FAST"
            print(f"  {service:<10}: {result*1000:.0f}ms  {status}")

asyncio.run(main())