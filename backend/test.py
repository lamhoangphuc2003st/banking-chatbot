import os
import json
import redis


class RedisCache:
    def __init__(self):
        self.client = redis.Redis.from_url(
            os.getenv("REDIS_URL"),
            decode_responses=True
        )
        self.ttl = 3600
        self.prefix = "rag:cache:"

    # -------------------------
    def _key(self, query):
        return f"{self.prefix}{query}"

    # -------------------------
    def get(self, query):
        data = self.client.get(self._key(query))

        if not data:
            return None

        return json.loads(data)

    # -------------------------
    def set(self, query, value):
        self.client.setex(
            self._key(query),
            self.ttl,
            json.dumps(value)
        )

    # -------------------------
    def delete(self, query):
        self.client.delete(self._key(query))

    # -------------------------
    def clear(self):
        """Xóa toàn bộ cache RAG (không ảnh hưởng redis khác)"""
        keys = self.client.keys(f"{self.prefix}*")

        if keys:
            self.client.delete(*keys)

    # -------------------------
    def clear_all(self):
        """Xóa toàn bộ Redis (danger)"""
        self.client.flushall()