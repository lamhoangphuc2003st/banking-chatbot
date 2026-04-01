import os
from qdrant_client import QdrantClient
from dotenv import load_dotenv
import json

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL")

client = QdrantClient(
    url=os.getenv("QDRANT_CLOUD_URL"),
    api_key=os.getenv("QDRANT_CLOUD_API_KEY"),
    prefer_grpc=False,
    timeout=60,
    check_compatibility=False
)

COLLECTION = "faq_cache"


def read_all_semantic_cache():

    offset = None
    total = 0

    while True:

        points, offset = client.scroll(
            collection_name=COLLECTION,
            limit=20,
            offset=offset,
            with_payload=True,
            with_vectors=False
        )

        if not points:
            break

        for p in points:
            payload = p.payload or {}

            print("=" * 80)
            print("ID:", p.id)
            print("\nQUERY:")
            print(payload.get("query"))

            print("\nCONTEXT:")
            print(payload.get("context")[:500], "...")

            total += 1

        if offset is None:
            break

    print(f"\nTotal semantic cache: {total}")


if __name__ == "__main__":
    read_all_semantic_cache()