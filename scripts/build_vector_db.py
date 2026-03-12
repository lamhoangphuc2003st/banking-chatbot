import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

CHUNK_PATH = "vietcombank_chunks.json"
INDEX_PATH = "faiss_index.bin"

EMBEDDING_MODEL = "bkai-foundation-models/vietnamese-bi-encoder"


def load_chunks():

    with open(CHUNK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def main():

    chunks = load_chunks()

    texts = [c["text"] for c in chunks]

    print("Loading embedding model...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print("Embedding chunks...")

    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True
    )

    embeddings = np.array(embeddings).astype("float32")

    dim = embeddings.shape[1]

    index = faiss.IndexFlatIP(dim)

    index.add(embeddings)

    print("Total vectors:", index.ntotal)

    faiss.write_index(index, INDEX_PATH)

    print("FAISS index saved")


if __name__ == "__main__":
    main()