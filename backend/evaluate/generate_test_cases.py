import json
import random
import csv
from pathlib import Path
import re

random.seed(42)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "vietcombank_chunks.json"

with open(DATA_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

# -----------------------------------------------------------------------
# Query templates — mỗi section/loại có nhiều variant để tránh bias
# -----------------------------------------------------------------------
LOAN_LIST_GLOBAL = [
    "Vietcombank có những gói vay nào?",
    "VCB có các sản phẩm vay gì?",
    "Danh sách sản phẩm vay của Vietcombank gồm những gì?",
    "Các nhóm vay tại Vietcombank bao gồm những gì?",
]

LOAN_LIST_BY_TYPE = [
    "Vietcombank có những gói vay {loan_type} nào?",
    "Các sản phẩm thuộc nhóm {loan_type} tại VCB?",
    "Nhóm vay {loan_type} gồm những sản phẩm gì?",
    "VCB có bao nhiêu gói vay {loan_type}?",
]

LOAN_THONG_TIN_CHUNG = [
    "Điều kiện vay {product} tại Vietcombank là gì?",
    "Đối tượng được vay {product} tại Vietcombank?",
    "Thời hạn vay tối đa {product} là bao lâu?",
    "Số tiền vay tối đa {product} tại Vietcombank?",
    "Ai đủ điều kiện vay {product} tại Vietcombank?",
    "Hạn mức vay {product} VCB là bao nhiêu?",
]

LOAN_HO_SO = [
    "Hồ sơ vay {product} tại Vietcombank cần những gì?",
    "Cần chuẩn bị giấy tờ gì để vay {product}?",
    "Thủ tục vay {product} Vietcombank gồm những tài liệu nào?",
    "Vay {product} cần nộp hồ sơ gì cho VCB?",
    "Giấy tờ cần thiết khi vay {product} Vietcombank?",
]

LOAN_QUY_TRINH = [
    "Quy trình vay {product} tại Vietcombank như thế nào?",
    "Các bước vay {product} tại Vietcombank?",
    "Lịch trả nợ vay {product} như thế nào?",
    "Kỳ hạn trả nợ vay {product} Vietcombank?",
    "Quy trình giải ngân {product} tại VCB?",
]

LOAN_BIEU_PHI = [
    "Phí trả nợ trước hạn {product} tại Vietcombank?",
    "Biểu phí vay {product} Vietcombank gồm những loại nào?",
    "Chi phí vay {product} có những khoản phí gì?",
    "Phí phạt trả nợ trước hạn {product}?",
]

LOAN_PHI = [
    "Phí vay {product} tại Vietcombank là bao nhiêu?",
    "Chi phí liên quan đến vay {product} VCB?",
]

CARD_LIST = [
    "Vietcombank có những loại thẻ tín dụng nào?",
    "VCB phát hành những thẻ tín dụng gì?",
    "Danh sách thẻ tín dụng Vietcombank hiện có?",
    "VCB có bao nhiêu loại thẻ tín dụng?",
]

CARD_OVERVIEW = [
    "Thẻ {product} có hạn mức tín dụng bao nhiêu?",
    "Thông tin sản phẩm thẻ {product} Vietcombank?",
    "Hạn mức sử dụng thẻ {product} là bao nhiêu?",
    "Giới thiệu về thẻ {product} của Vietcombank?",
    "Thẻ {product} VCB có những tính năng gì?",
]

CARD_CONDITION = [
    "Điều kiện mở thẻ {product} là gì?",
    "Ai được làm thẻ {product} Vietcombank?",
    "Yêu cầu để phát hành thẻ {product}?",
    "Điều kiện phát hành thẻ {product} VCB?",
    "Tôi cần đáp ứng điều kiện gì để mở thẻ {product}?",
]

CARD_FEE = [
    "Phí thường niên thẻ {product} là bao nhiêu?",
    "Biểu phí thẻ {product} Vietcombank gồm những gì?",
    "Phí phát hành thẻ {product} là bao nhiêu?",
    "Chi phí sử dụng thẻ {product} VCB?",
    "Thẻ {product} mất phí bao nhiêu mỗi năm?",
]

CARD_BENEFIT = [
    "Lợi ích thẻ {product} Vietcombank là gì?",
    "Thẻ {product} có những ưu đãi gì?",
    "Quyền lợi khi dùng thẻ {product} VCB?",
    "Thẻ {product} tích điểm thưởng như thế nào?",
    "Ưu đãi hoàn tiền thẻ {product} Vietcombank?",
]

CARD_EMPTY = [
    "Thẻ {product} Vietcombank có ưu đãi gì?",
    "Thông tin về thẻ {product} VCB?",
]


def pick(templates, **kwargs):
    return random.choice(templates).format(**kwargs)


def extract_qa_question(text: str) -> str:
    match = re.search(r"Câu hỏi:\s*(.*?)\s*Trả lời:", text, re.S)
    if match:
        return match.group(1).strip()[:200]
    return None


# -----------------------------------------------------------------------
# Generate
# -----------------------------------------------------------------------
test_cases = []

for doc in data:
    doc_id = doc["id"]
    meta = doc["metadata"]
    doc_type = meta.get("type", "")
    section = meta.get("section")
    product = meta.get("product_name", "")
    loan_type = meta.get("loan_type", "")
    text = doc["text"]

    # ✅ QA priority: luôn lấy từ "Câu hỏi:"
    query = extract_qa_question(text)

    section_label = section if section is not None else "__qa__"

    # nếu không phải QA thì mới generate template
    if not query:

        # ---- LOAN ----
        if doc_type == "loan":
            if section == "list" and not loan_type:
                query = pick(LOAN_LIST_GLOBAL)

            elif section == "list" and loan_type:
                query = pick(LOAN_LIST_BY_TYPE, loan_type=loan_type)

            elif section == "Thông tin chung" and product:
                query = pick(LOAN_THONG_TIN_CHUNG, product=product)

            elif section == "Hồ sơ chuẩn bị" and product:
                query = pick(LOAN_HO_SO, product=product)

            elif section in ("Quy trình & Ngày trả nợ", "Quy trình vay và kỳ trả nợ") and product:
                query = pick(LOAN_QUY_TRINH, product=product)

            elif section == "Biểu phí" and product:
                query = pick(LOAN_BIEU_PHI, product=product)

            elif section == "Phí" and product:
                query = pick(LOAN_PHI, product=product)

        # ---- CARD ----
        elif doc_type == "card":
            if section == "list":
                query = pick(CARD_LIST)

            elif section == "overview" and product:
                query = pick(CARD_OVERVIEW, product=product)

            elif section == "condition" and product:
                query = pick(CARD_CONDITION, product=product)

            elif section == "fee" and product:
                query = pick(CARD_FEE, product=product)

            elif section == "benefit" and product:
                query = pick(CARD_BENEFIT, product=product)

            elif section == "" and product:
                query = pick(CARD_EMPTY, product=product)

    if query:
        test_cases.append({
            "doc_id": doc_id,
            "query": query,
            "product": product or loan_type or "",
            "section": section_label,
            "type": doc_type,
        })
    else:
        # fallback — không bỏ sót doc nào
        fallback = f"Thông tin về {product or loan_type or 'sản phẩm Vietcombank'}?"
        test_cases.append({
            "doc_id": doc_id,
            "query": fallback,
            "product": product or loan_type or "",
            "section": section_label,
            "type": doc_type,
        })

# -----------------------------------------------------------------------
# Save
# -----------------------------------------------------------------------
with open(BASE_DIR/"evaluate"/"retrieval_test_cases.json", "w", encoding="utf-8") as f:
    json.dump(test_cases, f, ensure_ascii=False, indent=2)

with open(BASE_DIR/"evaluate"/"retrieval_test_cases.csv", "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["doc_id", "query", "product", "section", "type"])
    writer.writeheader()
    writer.writerows(test_cases)

print(f"Total test cases: {len(test_cases)}")
by_section = {}
for t in test_cases:
    s = t["section"]
    by_section[s] = by_section.get(s, 0) + 1
for s, c in sorted(by_section.items()):
    print(f"  {s:35s}: {c}")
