import json
import uuid

INPUT_PATH = "vietcombank_corpus.json"
OUTPUT_PATH = "vietcombank_chunks.json"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_chunk(doc):

    product = doc.get("product_name", "")
    text = doc.get("text", "")
    product_type = doc.get("product_type", "")

    metadata = doc.get("metadata", {})

    keywords = []

    if product_type == "loan":
        keywords = [
            "vay",
            "vay ngân hàng",
            "lãi suất",
            "điều kiện vay",
            "khoản vay"
        ]

    if product_type == "credit_card":
        keywords = [
            "thẻ tín dụng",
            "hạn mức",
            "phí thường niên",
            "mở thẻ"
        ]

    keyword_text = ", ".join(keywords)

    chunk_text = f"""
Ngân hàng: Vietcombank
Sản phẩm: {product}

Loại sản phẩm: {product_type}

Từ khóa liên quan: {keyword_text}

Nội dung:
{text}
"""

    return {
        "chunk_id": str(uuid.uuid4()),
        "doc_id": doc["doc_id"],
        "product_name": product,
        "product_type": product_type,
        "text": chunk_text.strip(),
        "metadata": metadata
    }


def main():

    corpus = load_json(INPUT_PATH)

    chunks = []

    for doc in corpus:
        chunk = create_chunk(doc)
        chunks.append(chunk)

    print("Total chunks:", len(chunks))

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print("Saved:", OUTPUT_PATH)


if __name__ == "__main__":
    main()