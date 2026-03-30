import redis
import os
from dotenv import load_dotenv
import json

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL")

client = redis.from_url(
    REDIS_URL,
    decode_responses=True
)

def read_all_cache():
    keys = client.keys("*")

    print(f"Total keys: {len(keys)}\n")

    for key in keys:
        value = client.get(key)

        print("="*80)
        print("KEY:", key)

        try:
            parsed = json.loads(value)
            print(json.dumps(parsed, indent=2, ensure_ascii=False))
        except:
            print("VALUE:", value)

if __name__ == "__main__":
    read_all_cache()