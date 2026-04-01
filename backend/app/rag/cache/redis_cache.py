import os
import json
import hashlib

import redis.asyncio as aioredis


class RedisCache:
    def __init__(self):
        # redis-py >= 4.2 ships redis.asyncio — no extra package needed
        self.client = aioredis.from_url(
            os.environ["REDIS_URL"],
            decode_responses=True
        )
        self.ttl = 86400
        self.prefix = "rag:cache:"

    def _key(self, query: str) -> str:
        return self.prefix + hashlib.md5(query.encode()).hexdigest()

    async def get(self, query: str):
        val = await self.client.get(self._key(query))
        return json.loads(val) if val else None

    async def set(self, query: str, value):
        await self.client.setex(
            self._key(query),
            self.ttl,
            json.dumps(value)
        )