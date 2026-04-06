import json
import uuid
import re
from pathlib import Path
from collections import defaultdict

# ======================
# CONFIG
# ======================
CHUNK_SIZE = 400
OVERLAP = 50

# ======================
# PATH SETUP
# ======================
# Thư mục chứa file chunker.py
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
RAW_DIR = PROJECT_DIR / "raw"
OUTPUT_DIR = SCRIPT_DIR
OUTPUT_DIR.mkdir(exist_ok=True)

# ======================
# UTILS
# ======================
def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=OVERLAP):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk.strip())
        start += chunk_size - overlap
    return chunks


def make_id():
    return str(uuid.uuid4())


def load_json(filename):
    path = RAW_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"❌ Không tìm thấy file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ======================
# 1. PROCESS FAQ (GENERAL)
# ======================
def process_faq_general(data):
    results = []

    for item in data:
        q = clean_text(item.get("question", ""))
        a = clean_text(item.get("answer", ""))

        full_text = f"Câu hỏi: {q} Trả lời: {a}"

        # ✅ chỉ 1 chunk
        results.append({
            "id": make_id(),
            "text": full_text,
            "metadata": {
                "type": "card",
                "card_type": "credit_card"
            }
        })

    return results


# ======================
# 2. PROCESS LOAN FAQ
# ======================
def process_loan_faq(data):
    results = []

    for cat in data:
        category = cat.get("category", "")

        for qa in cat.get("questions", []):
            q = clean_text(qa.get("question", ""))
            a = clean_text(qa.get("answer", ""))

            full_text = f"Câu hỏi: {q} Trả lời: {a}"

            # Chỉ 1 chunk
            results.append({
                "id": make_id(),
                "text": full_text,
                "metadata": {
                    "type": "loan",
                    "product_name": category
                }
            })

    return results


# ======================
# 3. PROCESS LOANS
# ======================
def process_loans(data):
    results = []

    for loan in data:
        loan_type = loan.get("loan_type", "")
        loan_name = loan.get("name", "")
        detail = loan.get("detail", {})

        for section_name, section_content in detail.items():

            if not isinstance(section_content, dict):
                continue

            parts = []

            for key, values in section_content.items():
                if isinstance(values, list):
                    parts.append(f"{key}: {'; '.join(values)}")
                else:
                    parts.append(f"{key}: {values}")

            text = f"{loan_name}: {section_name}: " + " | ".join(parts)
            text = clean_text(text)

            #Chỉ 1 chunk
            results.append({
                "id": make_id(),
                "text": text,
                "metadata": {
                    "type": "loan",
                    "loan_type": loan_type,
                    "product_name": loan_name,
                    "section": section_name
                }
            })

    return results


# ======================
# 4. PROCESS CREDIT CARDS
# ======================
def process_cards(data):

    SECTION_MAP = {
        "Lợi ích": "benefit",
        "Điều kiện mở thẻ": "condition",
        "Biểu phí": "fee",
        "Thông tin sản phẩm": "overview",
        "title": "title"
    }

    results = []

    for card in data:
        name = card.get("name", "")
        detail = card.get("detail", {})

        for section, content in detail.items():

            if section == "title":
                continue

            section_en = SECTION_MAP.get(section, section)

            parts = []

            if isinstance(content, dict):
                for key, values in content.items():
                    if isinstance(values, list):
                        parts.append(f"{key}: {'; '.join(values)}")
                    else:
                        parts.append(f"{key}: {values}")
            else:
                parts.append(str(content))

            text = f"Thẻ {name}: {section}: " + " | ".join(parts)
            text = clean_text(text)

            #Chỉ 1 chunk
            results.append({
                "id": make_id(),
                "text": text,
                "metadata": {
                    "type": "card",
                    "card_type": "credit_card",
                    "product_name": name,
                    "section": section_en
                }
            })

    return results


def build_product_list(loans, cards):
    results = []

    # ===== LOAN LIST =====
    loan_map = defaultdict(list)

    for loan in loans:
        loan_type = loan.get("loan_type", "").strip()
        loan_name = loan.get("name", "").strip()

        if loan_type and loan_name:
            if loan_name not in loan_map[loan_type]:
                loan_map[loan_type].append(loan_name)

    # build text
    parts = []
    for loan_type, names in loan_map.items():
        names_str = ", ".join(names)
        parts.append(f"{loan_type}: {names_str}")

    loan_text = "Danh sách các sản phẩm vay của Vietcombank gồm: " + " | ".join(parts)

    results.append({
        "id": make_id(),
        "text": loan_text,
        "metadata": {
            "type": "loan",
            "section": "list"
        }
    })

    for loan_type, names in loan_map.items():
        names_str = " | ".join(names)

        text = f"Các gói vay thuộc nhóm {loan_type} của Vietcombank gồm: {names_str}"

        results.append({
            "id": make_id(),
            "text": text,
            "metadata": {
                "type": "loan",
                "loan_type": loan_type,
                "section": "list"
            }
        })

    # ===== CARD LIST =====
    card_names = [card.get("name", "") for card in cards]
    card_text = "Các loại thẻ tín dụng Vietcombank gồm: " + ", ".join(card_names)

    results.append({
        "id": make_id(),
        "text": card_text,
        "metadata": {
            "type": "card",
            "section": "list"
        }
    })

    return results


# ======================
# MAIN
# ======================
def main():
    all_chunks = []

    # LOAD FILES (từ crawler/raw/)
    card_faq = load_json("vietcombank_credit_faq.json")
    loan_faq = load_json("vietcombank_loan_faq.json")
    loans = load_json("vietcombank_loans.json")
    cards = load_json("vietcombank_credit_cards.json")

    # PROCESS
    all_chunks.extend(build_product_list(loans, cards))
    all_chunks.extend(process_loans(loans))
    all_chunks.extend(process_loan_faq(loan_faq))
    all_chunks.extend(process_cards(cards))
    all_chunks.extend(process_faq_general(card_faq))
    
    # SAVE OUTPUT
    output_path = OUTPUT_DIR / "vietcombank_chunks.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print(f"Done! Total chunks: {len(all_chunks)}")
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()