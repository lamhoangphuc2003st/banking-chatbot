import json
import faiss
import numpy as np
from rank_bm25 import BM25Okapi

from langchain_openai import OpenAIEmbeddings
from app.rag.retrieval.rrf import rrf_fusion


class HybridRetriever:

    def __init__(self, chunks_path, faiss_path):

        with open(chunks_path, "r", encoding="utf-8") as f:
            self.chunks = json.load(f)

        texts = [c["text"] for c in self.chunks]

        tokenized = [t.split() for t in texts]

        self.bm25 = BM25Okapi(tokenized)

        self.index = faiss.read_index(faiss_path)

        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-large"
        )

    def embed(self, query):

        emb = self.embeddings.embed_query(query)

        return np.array([emb]).astype("float32")

    def vector_search(self, query, k=10):

        q = self.embed(query)

        scores, ids = self.index.search(q, k)

        docs = []

        for idx in ids[0]:

            if idx >= len(self.chunks):
                continue

            docs.append(self.chunks[idx])

        return docs

    def bm25_search(self, query, k=10):

        tokens = query.split()

        scores = self.bm25.get_scores(tokens)

        ranked = sorted(
            enumerate(scores),
            key=lambda x: x[1],
            reverse=True
        )[:k]

        docs = []

        for idx,_ in ranked:
            docs.append(self.chunks[idx])

        return docs

    def search(self, query):

        vec = self.vector_search(query)

        bm = self.bm25_search(query)

        fused_ids = rrf_fusion([vec,bm])

        docs = []

        for i in fused_ids[:20]:

            for c in self.chunks:
                if c["doc_id"] == i:
                    docs.append(c)

        return docs