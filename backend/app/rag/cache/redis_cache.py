import os
import redis
import json
import hashlib

class RedisCache:
    def __init__(self):
        self.client = redis.from_url(
            os.environ["REDIS_URL"],
            decode_responses=True
        )
        self.ttl = 86400
        self.prefix = "rag:cache:"

    def _key(self, query):
        return self.prefix + hashlib.md5(query.encode()).hexdigest()

    def get(self, query):
        val = self.client.get(self._key(query))
        return json.loads(val) if val else None

    def set(self, query, value):
        self.client.setex(
            self._key(query),
            self.ttl,
            json.dumps(value)
        )