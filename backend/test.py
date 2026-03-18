import redis
import os
from dotenv import load_dotenv

load_dotenv()

r = redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)

# SET
r.set("test_key", "hello_redis", ex=60)

# GET
value = r.get("test_key")

print("Value:", value)