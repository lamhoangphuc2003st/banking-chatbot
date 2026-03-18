from app.rag.utils.logger import get_logger

logger = get_logger(__name__)


class ContextCompressor:

    def __init__(self):

        self.max_docs = 8
        self.min_length = 30

    def compress(self, docs):

        if not docs:
            return docs

        compressed = []
        seen_text = set()

        for d in docs:

            text = (d.get("text") or "").strip()

            if len(text) < self.min_length:
                continue

            # remove duplicate chunks
            if text in seen_text:
                continue

            seen_text.add(text)

            compressed.append(d)

        # limit number of docs
        compressed = compressed[:self.max_docs]

        logger.info(f"Context compressed: {len(docs)} → {len(compressed)}")

        return compressed