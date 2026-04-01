import re
import unicodedata
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0
)


# ============================================================
# UTILS
# ============================================================

def _normalize(text: str) -> str:
    """
    Bỏ dấu tiếng Việt + lowercase. Match cả khi user gõ thiếu dấu.
    Xử lý đặc biệt: đ (U+0111) không decompose qua NFKD nên phải replace thủ công.
    """
    nfkd = unicodedata.normalize("NFKD", text.lower())
    result = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Ký tự tiếng Việt không decompose qua NFKD
    result = result.replace("đ", "d").replace("ð", "d")
    return result


# ============================================================
# LAYER 1A: KHÔNG BAO GIỜ MƠ HỒ — Discovery / List
# ============================================================

# Pattern: "VCB có ... không", "có dịch vụ ... không", etc.
_DISCOVERY_PATTERNS = [
    r"có\s+.{0,50}không",
    r"vcb\s+có",
    r"vietcombank\s+có",
    r"ngân hàng\s+có",
    r"có\s+cung cấp",
    r"có\s+dịch vụ",
    r"có\s+cho vay",
    r"có\s+hỗ trợ",
    r"có\s+sản phẩm",
    r"có\s+gói",
    r"có\s+thẻ",
    # no-diacritics versions
    r"co\s+.{0,50}khong",
    r"vcb\s+co",
    r"vietcombank\s+co",
    r"ngan hang\s+co",
    r"co\s+cung cap",
    r"co\s+dich vu",
    r"co\s+cho vay",
    r"co\s+goi",
    r"co\s+the",
]

# Pattern: câu hỏi liệt kê danh sách — "các gói nào", "bao nhiêu loại", "tất cả thẻ"
_LIST_PATTERNS = [
    r"(các|những)\s+.{0,30}(là gì|nào|gì|có gì)",
    r"(tất cả|toàn bộ|danh sách|liệt kê)",
    r"bao nhiêu\s+(loại|gói|sản phẩm|thẻ)",
    r"(loại|gói|sản phẩm|thẻ)\s+nào",
    r"có\s+(những|các)\s+gì",
    # no-diacritics
    r"(cac|nhung)\s+.{0,30}(la gi|nao|gi|co gi)",
    r"(tat ca|toan bo|danh sach|liet ke)",
    r"bao nhieu\s+(loai|goi|san pham|the)",
    r"(loai|goi|san pham)\s+nao",  # "the" excluded: collides with "the nao" (how)
]


def _is_discovery_or_list(query: str) -> bool:
    q_orig = query.lower()
    q_norm = _normalize(query)
    for p in _DISCOVERY_PATTERNS + _LIST_PATTERNS:
        if re.search(p, q_orig) or re.search(p, q_norm):
            return True
    return False


# ============================================================
# LAYER 1B: KHÔNG MƠ HỒ nếu không có từ khóa chi tiết
# ============================================================

_DETAIL_KEYWORDS = [
    # Điều kiện / yêu cầu / đối tượng
    "điều kiện", "yêu cầu", "tiêu chuẩn", "tiêu chí",
    "đối tượng", "đối tượng vay", "ai được vay", "ai có thể vay",
    "đối tượng khách hàng",
    # Hồ sơ / giấy tờ
    "hồ sơ", "giấy tờ", "tài liệu", "chứng từ",
    "cần gì", "cần những gì", "cần có gì", "cần chuẩn bị",
    # Phí / chi phí
    "phí", "chi phí", "mức phí", "phí dịch vụ",
    "phí thường niên", "phí phát hành", "phí rút tiền",
    "phí chuyển đổi", "phí tất toán", "phí trả trước",
    # Lãi suất
    "lãi suất", "lãi", "lãi vay", "lãi tín dụng",
    "ls", "lãi hàng tháng", "lãi hàng năm",
    # Thủ tục / quy trình
    "thủ tục", "quy trình", "các bước", "bước",
    "đăng ký", "đăng ký như thế nào", "làm thế nào để",
    "thẩm định", "giải ngân",
    # Thời hạn / hạn mức
    "thời hạn", "hạn mức", "mức vay", "mức tín dụng",
    "vay tối đa", "vay tối thiểu", "kỳ hạn",
    "hạn mức thẻ", "hạn mức tín dụng",
    # Lợi ích / ưu đãi
    "lợi ích", "ưu đãi", "quyền lợi", "tính năng",
    "khuyến mãi", "quà tặng", "điểm thưởng", "cashback",
    "hoàn tiền", "ưu đãi lãi suất",
    # So sánh
    "so sánh", "khác nhau", "giống nhau", "tốt hơn",
    "nên chọn", "nên vay", "phù hợp",
]


def _has_detail_keyword(query: str) -> bool:
    q = _normalize(query)
    return any(_normalize(k) in q for k in _DETAIL_KEYWORDS)


# ============================================================
# LAYER 1C: KHÔNG MƠ HỒ nếu đã có tên sản phẩm cụ thể
# ============================================================

# Danh mục chung — KHÔNG phải tên sản phẩm
_GENERIC_CATEGORIES = [
    # Vay
    "vay tiêu dùng", "vay kinh doanh", "vay mua nhà", "vay mua xe",
    "vay sản xuất", "vay mua bất động sản", "vay thế chấp",
    "vay tín chấp", "vay có tài sản", "cho vay",
    # Thẻ
    "thẻ tín dụng", "thẻ ghi nợ", "thẻ thanh toán",
    "thẻ ngân hàng", "thẻ atm", "thẻ visa", "thẻ mastercard",
    "thẻ debit", "thẻ credit",
    # Chung
    "tiết kiệm", "tài khoản", "bảo hiểm", "chuyển tiền",
    "thanh toán", "gửi tiền",
    "vay", "thẻ", "gói",
]

# Từ phụ trợ cần loại bỏ (không phải tên SP)
_FILLER_WORDS = [
    # Từ hỏi
    "là gì", "bao nhiêu", "thế nào", "như thế nào", "ra sao",
    "ở đâu", "khi nào", "bao lâu",
    "không", "gì",
    # Tên tổ chức
    "vietcombank", "vcb", "ngân hàng",
    # Giới từ / liên từ
    "của", "tại", "để", "cho", "và", "hoặc", "với",
    "về", "theo", "trong", "trên", "dưới", "từ", "đến",
    "khi", "nếu", "thì", "được", "cần",
    "so với", "so sánh với",
    # Đại từ / xưng hô
    "tôi", "bạn", "mình", "em", "anh", "chị",
    # Động từ chung
    "sử dụng", "dùng", "muốn", "cần", "muốn biết",
    "tìm hiểu", "hỏi", "biết", "hiểu",
    "khi sử dụng", "khi dùng", "khi mua", "khi vay",
    # Tính từ chung
    "mới", "cũ", "hiện tại", "hiện nay",
    # Đại từ chỉ định
    "này", "đó", "kia", "đây", "đó",
    # Trạng từ
    "thường", "thường xuyên", "hay", "tất cả",
]


# Whitelist tên sản phẩm cụ thể — cập nhật khi có sản phẩm mới
# Đồng bộ với danh sách trong _extract_prompt bên dưới
_SPECIFIC_PRODUCTS = [
    # Vay tiêu dùng
    "vay tín chấp theo lương", "vay cầm cố giấy tờ có giá",
    "vay tiêu dùng có tài sản bảo đảm",
    # Vay kinh doanh
    "an tâm kinh doanh", "kinh doanh tài lộc",
    "vay xây mới cơ sở lưu trú du lịch",
    "vay nâng cấp cơ sở lưu trú du lịch",
    # Vay bất động sản
    "vay xây sửa nhà ở", "nhà mới thành đạt",
    "vay mua nhà dự án", "vay mua nhà ở đất ở",
    "vay mua nhà ở", "vay mua đất ở",
    # Thẻ
    "visa platinum", "visa classic", "visa infinite",
    "mastercard platinum", "mastercard world",
    "vcb digicard", "jcb platinum",
]


def _has_specific_product(query: str) -> bool:
    """
    Whitelist-based: khớp trực tiếp với tên sản phẩm cụ thể.
    Chính xác hơn approach strip-keyword, không có false-positive.
    """
    q = _normalize(query)
    return any(_normalize(p) in q for p in _SPECIFIC_PRODUCTS)


# NOTE: Layer 1D (_is_user_selecting) đã được chuyển vào pipeline.py
# dưới dạng RAGPipeline._last_bot_was_clarification() — check ở đó trước khi
# gọi _invoke_clarify, giữ logic ở một chỗ duy nhất.


# ============================================================
# MAIN: is_ambiguous_by_rule
# ============================================================

def is_ambiguous_by_rule(query: str, history=None) -> bool:
    """
    Trả về True CHỈ KHI:
    1. Không phải câu khám phá / liệt kê
    2. Có từ khóa chi tiết (điều kiện, phí, lãi suất, hồ sơ, đối tượng...)
    3. Không có tên sản phẩm cụ thể trong whitelist
    (Layer 0: user đang trả lời clarify → check bởi pipeline._last_bot_was_clarification)
    (Layer 2: history có ≥2 sản phẩm → check bởi pipeline._invoke_clarify)
    """
    if _is_discovery_or_list(query):
        return False

    if not _has_detail_keyword(query):
        return False

    if _has_specific_product(query):
        return False

    return True


# ============================================================
# LAYER 2: LLM — Extract sản phẩm từ history
# ============================================================

_extract_prompt = ChatPromptTemplate.from_template(
"""
Trích xuất danh sách tên sản phẩm/dịch vụ CỤ THỂ được nhắc đến trong lịch sử hội thoại.

Sản phẩm VCB thường gặp (để tham khảo nhận dạng):
- Vay: "Vay tín chấp theo lương", "Vay cầm cố giấy tờ có giá", "Vay tiêu dùng có tài sản bảo đảm",
       "An tâm kinh doanh", "Kinh doanh tài lộc", "Vay xây mới cơ sở lưu trú du lịch",
       "Vay nâng cấp cơ sở lưu trú du lịch", "Vay mua nhà", "Vay mua xe"
- Thẻ: "Visa Platinum", "Visa Classic", "MasterCard Platinum", "VCB DigiCard"

Quy tắc:
- Chỉ lấy tên sản phẩm/gói CỤ THỂ — KHÔNG lấy danh mục chung ("vay tiêu dùng", "thẻ tín dụng")
- Chỉ lấy từ lịch sử hội thoại bên dưới, KHÔNG tự thêm
- Nếu không có: trả về []

Lịch sử hội thoại:
{history}

Trả về JSON (KHÔNG markdown, KHÔNG backtick):
{{"products": ["Tên sản phẩm 1", "Tên sản phẩm 2"]}}
"""
)

extract_products_chain = _extract_prompt | llm | JsonOutputParser()


# ============================================================
# LAYER 3: BUILD MESSAGE
# ============================================================

def build_clarification_message(mentioned_products: list[str]) -> str:
    base = "Bạn muốn hỏi về sản phẩm/dịch vụ nào?"
    if not mentioned_products:
        return base + " Vui lòng cho tôi biết tên sản phẩm hoặc dịch vụ bạn quan tâm."
    suggestions = "\n".join(f"- {p}" for p in mentioned_products)
    return (
        f"{base} Dựa trên cuộc trò chuyện, bạn có thể đang hỏi về:\n\n"
        f"{suggestions}\n\n"
        "Bạn muốn tìm hiểu về sản phẩm nào?"
    )