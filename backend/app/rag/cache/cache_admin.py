"""
cache_admin.py — Tiện ích xóa cache theo query text.

Dùng 2 cách:
  1. Script trực tiếp: python cache_admin.py "Điều kiện vay xây sửa nhà ở tại Vietcombank là gì?"
  2. Gắn router vào FastAPI app: app.include_router(cache_router)
"""

import asyncio
import hashlib
import os
import sys
from pathlib import Path

# Load .env tự động — tìm ngược lên từ thư mục hiện tại
try:
    from dotenv import load_dotenv
    for parent in [Path.cwd(), *Path.cwd().parents]:
        env_file = parent / ".env"
        if env_file.exists():
            load_dotenv(env_file)
            break
except ImportError:
    pass  # python-dotenv chưa cài — env vars phải set thủ công

import redis.asyncio as aioredis
from qdrant_client import AsyncQdrantClient
from langchain_openai import OpenAIEmbeddings
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


# -------------------------
# Core invalidation logic
# -------------------------

async def delete_redis(query: str) -> bool:
    """Xóa 1 key khỏi Redis theo query text. Trả về True nếu key tồn tại và đã xóa."""
    client = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    key = "rag:cache:" + hashlib.md5(query.encode()).hexdigest()
    deleted = await client.delete(key)
    await client.aclose()
    return bool(deleted)


async def delete_semantic(query: str, threshold: float = 0.92) -> int:
    """
    Tìm và xóa điểm trong faq_cache Qdrant có vector gần với query (score >= threshold).
    threshold cao (0.98) để chỉ xóa đúng câu đó, không ảnh hưởng câu tương tự.
    Trả về số điểm đã xóa.
    """
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    vector = await embeddings.aembed_query(query)

    client = AsyncQdrantClient(
        url=os.getenv("QDRANT_CLOUD_URL"),
        api_key=os.getenv("QDRANT_CLOUD_API_KEY"),
        prefer_grpc=False,
        timeout=60,
    )

    results = await client.query_points(
        collection_name="faq_cache",
        query=vector,
        limit=5,
        with_payload=True,
        with_vectors=False,
    )

    ids_to_delete = [
        r.id for r in results.points
        if r.score >= threshold
    ]

    if ids_to_delete:
        await client.delete(
            collection_name="faq_cache",
            points_selector=ids_to_delete,
        )

    await client.close()
    return len(ids_to_delete)


async def invalidate(query: str) -> dict:
    """Xóa đồng thời khỏi Redis và Qdrant semantic cache."""
    redis_deleted, semantic_deleted = await asyncio.gather(
        delete_redis(query),
        delete_semantic(query),
    )
    return {
        "query": query,
        "redis_deleted": redis_deleted,
        "semantic_deleted": semantic_deleted,
    }


# -------------------------
# FastAPI router (optional)
# -------------------------

cache_router = APIRouter(prefix="/admin/cache", tags=["cache"])


class InvalidateRequest(BaseModel):
    query: str          # query text đã được rewrite (như trong log: "Rewrite: ...")
    threshold: float = 0.98


@cache_router.delete("/invalidate")
async def invalidate_cache(req: InvalidateRequest):
    """
    Xóa cache của 1 query cụ thể khỏi Redis và Qdrant semantic cache.

    Body:
      query    — rewritten query, lấy từ log dòng "Rewrite: ..."
      threshold — độ tương đồng tối thiểu để xóa semantic (mặc định 0.98)

    Ví dụ:
      DELETE /admin/cache/invalidate
      {"query": "Điều kiện vay xây sửa nhà ở tại Vietcombank là gì?"}
    """
    try:
        redis_deleted, semantic_deleted = await asyncio.gather(
            delete_redis(req.query),
            delete_semantic(req.query, req.threshold),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not redis_deleted and semantic_deleted == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy cache cho query: {req.query}"
        )

    return {
        "query": req.query,
        "redis_deleted": redis_deleted,
        "semantic_deleted": semantic_deleted,
    }


@cache_router.delete("/flush")
async def flush_semantic_cache():
    """Xóa TOÀN BỘ faq_cache trong Qdrant. Dùng khi cần reset sạch."""
    client = AsyncQdrantClient(
        url=os.getenv("QDRANT_CLOUD_URL"),
        api_key=os.getenv("QDRANT_CLOUD_API_KEY"),
        prefer_grpc=False,
        timeout=60,
    )
    info = await client.get_collection("faq_cache")
    count = info.points_count
    await client.delete_collection("faq_cache")
    await client.close()
    return {"flushed": True, "points_deleted": count}

async def flush_redis():
    client = aioredis.from_url(os.environ["REDIS_URL"], decode_responses=True)

    keys = []
    async for key in client.scan_iter("rag:cache:*"):
        keys.append(key)

    if keys:
        await client.delete(*keys)

    await client.aclose()
    return len(keys)

@cache_router.delete("/flush-all")
async def flush_all():
    redis_deleted = await flush_redis()

    client = AsyncQdrantClient(
        url=os.getenv("QDRANT_CLOUD_URL"),
        api_key=os.getenv("QDRANT_CLOUD_API_KEY"),
    )

    info = await client.get_collection("faq_cache")
    count = info.points_count

    await client.delete_collection("faq_cache")
    await client.close()

    return {
        "redis_deleted": redis_deleted,
        "qdrant_deleted": count
    }


# -------------------------
# CLI usage
# -------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python cache_admin.py <query>")
        print("  python cache_admin.py flush-redis")
        print("  python cache_admin.py flush-qdrant")
        print("  python cache_admin.py flush-all")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "flush-all":
        result = asyncio.run(flush_all())
        print("\nFLUSH ALL")
        print(f"Redis deleted  : {result['redis_deleted']}")
        print(f"Qdrant deleted : {result['qdrant_deleted']}")

    elif cmd == "flush-redis":
        count = asyncio.run(flush_redis())
        print(f"\nRedis deleted: {count}")

    elif cmd == "flush-qdrant":
        result = asyncio.run(flush_semantic_cache())
        print(f"\nQdrant deleted: {result['points_deleted']}")

    else:
        query = cmd
        result = asyncio.run(invalidate(query))

        print(f"\nQuery    : {result['query']}")
        print(f"Redis    : {'✓ đã xóa' if result['redis_deleted'] else '✗ không có'}")
        print(f"Semantic : {result['semantic_deleted']} điểm đã xóa")