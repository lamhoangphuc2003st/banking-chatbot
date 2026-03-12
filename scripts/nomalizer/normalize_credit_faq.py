import json
import re

INPUT_FILE = "../data/raw/vietcombank_credit_faq.json"
OUTPUT_FILE = "../data/normalized/vietcombank_credit_faq_normalized.json"


def map_topic(question: str) -> str:
    q = question.lower()

    if "phí" in q:
        return "fee"
    if "hạn mức" in q:
        return "limit"
    if "thanh toán" in q:
        return "payment"
    if "moca" in q:
        return "moca"
    if "3d secure" in q:
        return "security"
    if "mất thẻ" in q or "khóa thẻ" in q:
        return "card_security"

    return "general"


def normalize_credit_faq(raw_data):
    normalized = []

    for idx, item in enumerate(raw_data, start=1):
        question = item.get("question", "").strip()
        answer = item.get("answer", "").strip()
        topic = map_topic(question)

        faq_id = f"{topic}_{idx:03d}"

        full_text = (
            "Ngân hàng Vietcombank. "
            "Sản phẩm: Thẻ tín dụng. "
            f"Câu hỏi: {question} "
            f"Trả lời: {answer}"
        )

        record = {
            "bank": "vietcombank",
            "product_type": "credit_card",
            "document_type": "faq",
            "faq_id": faq_id,
            "question": question,
            "answer": answer,
            "full_text": full_text,
            "metadata": {
                "topic": topic,
                "source_url": item.get("url"),
                "original_id": item.get("id")
            }
        }

        normalized.append(record)

    return normalized


def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    normalized_data = normalize_credit_faq(raw_data)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(normalized_data, f, ensure_ascii=False, indent=2)

    print(f"Normalized {len(normalized_data)} records → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()