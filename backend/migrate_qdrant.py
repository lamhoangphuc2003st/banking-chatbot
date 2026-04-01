from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
import os
from dotenv import load_dotenv
from qdrant_client.models import PointStruct

load_dotenv()

src = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    port=None,
    prefer_grpc=False,
    timeout=60
)

# target (Qdrant Cloud)
dst = QdrantClient(
    url=os.getenv("QDRANT_CLOUD_URL"),
    api_key=os.getenv("QDRANT_CLOUD_API_KEY")
)

collections = ["vietcombank", "faq_cache"]

for collection in collections:

    print(f"Migrating {collection}...")

    # get collection info
    info = src.get_collection(collection)
    size = info.config.params.vectors.size
    distance = info.config.params.vectors.distance

    # reset collection cloud
    if dst.collection_exists(collection):
        print(f"Deleting old collection {collection}...")
        dst.delete_collection(collection)

    print(f"Creating collection {collection}...")
    dst.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(
            size=size,
            distance=distance
        )
    )

    offset = None

    while True:

        result = src.scroll(
            collection_name=collection,
            limit=200,
            offset=offset,
            with_payload=True,
            with_vectors=True
        )

        points = result[0]
        offset = result[1]

        if len(points) == 0:
            break

        converted = [
            PointStruct(
                id=p.id,
                vector=p.vector,
                payload=p.payload
            )
            for p in points
        ]

        dst.upsert(
            collection_name=collection,
            points=converted
        )

        print(f"Copied {len(points)}")

        if offset is None:
            break

print("Migration done!")