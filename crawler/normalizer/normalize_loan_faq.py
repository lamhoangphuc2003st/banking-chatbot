import json
import re
from typing import List, Dict, Any


INPUT_FILE = "../data/raw/vietcombank_loan_faq.json"
OUTPUT_FILE = "../data/normalized/vietcombank_loan_faq_normalized.json"


# ===============================
# Utility
# ===============================

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text.strip("-")


# ===============================
# Normalize Function
# ===============================

def normalize_loan_faq(raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized_records = []

    for category_block in raw_data:
        category_name = category_block.get("category", "").strip()
        product_id = slugify(category_name)

        questions = category_block.get("questions", [])

        for idx, qa in enumerate(questions, start=1):
            question = qa.get("question", "").strip()
            answer = qa.get("answer", "").strip()

            faq_id = f"{product_id}_{idx:02d}"

            full_text = (
                f"{category_name} - Câu hỏi: {question} "
                f"Trả lời: {answer}"
            )

            record = {
                "bank": "vietcombank",
                "product_type": "loan",
                "product_id": product_id,
                "product_name": category_name,

                "faq_id": faq_id,

                "question": question,
                "answer": answer,

                "full_text": full_text,

                "metadata": {
                    "category": category_name
                }
            }

            normalized_records.append(record)

    return normalized_records


# ===============================
# Main
# ===============================

def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    normalized = normalize_loan_faq(raw_data)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)

    print(f"Normalized {len(normalized)} FAQ records → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()