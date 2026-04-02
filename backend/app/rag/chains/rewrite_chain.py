from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from app.rag.llm_client import llm

# -----------------------------
# Convert history to text
# -----------------------------
def format_history(history):
    if not history:
        return ""
    lines = []
    for h in history[-5:]:
        role = "Người dùng" if h["role"] == "user" else "Trợ lý"
        lines.append(f"{role}: {h['content']}")
    return "\n".join(lines)


history_formatter = RunnableLambda(
    lambda x: format_history(x.get("history"))
)


# -----------------------------
# Prompt
# -----------------------------
prompt = ChatPromptTemplate.from_template(
"""
Bạn là hệ thống rewrite query cho chatbot ngân hàng Vietcombank.
Nhiệm vụ: Viết lại câu hỏi thành 1 câu đầy đủ, rõ nghĩa, tối ưu cho tìm kiếm tài liệu.
Chỉ trả về câu hỏi đã viết lại. Không giải thích.

---
BƯỚC 1 — XÁC ĐỊNH LOẠI CÂU HỎI

Phân loại câu hỏi theo thứ tự ưu tiên dưới đây:

[LOẠI A] Câu có TÊN SẢN PHẨM CỤ THỂ ngay trong câu hỏi hiện tại
  Dấu hiệu: chứa tên sản phẩm như "vay mua ô tô", "VCB-iB@nking", "thẻ Visa Platinum",
             "tài khoản thanh toán", "gói Flexi", "vay tín chấp CBNV"...
  Hành động: Sửa lỗi chính tả, chuẩn hóa tên sản phẩm, thêm "tại Vietcombank" nếu thiếu.
  Ví dụ:
    "vay mua o to dieu kien gi" → "Điều kiện vay mua ô tô tại Vietcombank là gì?"
    "thẻ visa platium phí thường niên bao nhiêu" → "Phí thường niên thẻ Visa Platinum Vietcombank là bao nhiêu?"

[LOẠI B] Câu có THAM CHIẾU ĐẾN SẢN PHẨM ĐÃ NHẮC trong lịch sử
  Dấu hiệu: chứa "gói đó", "sản phẩm đó", "cái đó", "các gói trên", "sản phẩm trên",
             "những gói này", "4 gói trên", đại từ thay thế cho sản phẩm cụ thể...
  Hành động:
    1. Tìm trong lịch sử — ưu tiên TRỢ LÝ nói gần nhất, lấy tên sản phẩm được liệt kê
    2. Thay thế tham chiếu mơ hồ bằng tên sản phẩm thực tế
    3. Nếu có nhiều sản phẩm → liệt kê hết, dùng dấu phẩy ngăn cách
  Ví dụ:
    [Lịch sử: Trợ lý vừa liệt kê "Vay mua ô tô, Vay tín chấp CBNV"]
    "gói đó lãi suất bao nhiêu" → "Lãi suất vay mua ô tô và vay tín chấp CBNV tại Vietcombank là bao nhiêu?"
    "4 gói trên điều kiện gì" → "Điều kiện của [SP1], [SP2], [SP3], [SP4] tại Vietcombank là gì?"

  ❌ TUYỆT ĐỐI KHÔNG được tự thêm tên sản phẩm không có trong lịch sử
  ❌ Nếu lịch sử không có sản phẩm nào → xử lý như LOẠI C

      Câu CHUYỂN CHỦ ĐỀ sang sản phẩm/danh mục mới
  Dấu hiệu: bắt đầu bằng "còn", "vậy còn", "thế còn" VÀ ngay sau đó là tên sản phẩm/danh mục
             VÍ DỤ: "Còn vay nhu cầu bất động sản thì sao"
                    "Thế còn thẻ tín dụng thì sao"
                    "Vậy còn vay mua xe?"
  Hành động: ưu tiên tên sản phẩm/danh mục TRONG CÂU HIỆN TẠI,
             KHÔNG lấy sản phẩm từ history
             Kết hợp với ý của câu hỏi (hỏi điều kiện? phí? hay chỉ hỏi có/không?)
  Ví dụ:
    [History: đang nói về vay tiêu dùng]
    "Còn vay nhu cầu bất động sản thì sao" → "Vietcombank có cho vay nhu cầu bất động sản không?"
    "Thế còn thẻ Visa Platinum phí bao nhiêu" → "Phí thẻ Visa Platinum tại Vietcombank là bao nhiêu?"

[LOẠI C] Câu THIẾU ĐỐI TƯỢNG — không có tên sản phẩm trong câu lẫn trong lịch sử
  Dấu hiệu: hỏi về điều kiện/phí/lãi suất/thủ tục/hồ sơ... mà không có tên sản phẩm
  Hành động: Chỉ sửa lỗi chính tả, chuẩn hóa ngữ pháp, thêm "tại Vietcombank"
             KHÔNG tự thêm tên sản phẩm dù context có vẻ liên quan
  Ví dụ:
    "dieu kien vay la gi" → "Điều kiện vay tại Vietcombank là gì?"
    "phí là bao nhiêu" → "Phí dịch vụ tại Vietcombank là bao nhiêu?"
    "lãi suất thế nào" → "Lãi suất tại Vietcombank là bao nhiêu?"

[LOẠI D] Câu là CÂU TRẢ LỜI cho câu hỏi làm rõ sản phẩm
  Dấu hiệu: lịch sử có tin nhắn trợ lý dạng "Bạn muốn tìm hiểu về sản phẩm nào?"
            VÀ câu hỏi hiện tại là tên sản phẩm (hoặc chỉ có tên sản phẩm)
  Hành động:
    1. Tìm câu hỏi GỐC của user TRƯỚC khi bot hỏi làm rõ (nhìn lùi về trước trong lịch sử)
    2. Kết hợp: [nội dung câu hỏi gốc] + [tên sản phẩm user vừa chọn] + "tại Vietcombank"
    3. Nếu không tìm được câu hỏi gốc → dùng tên sản phẩm + "tại Vietcombank là gì?"
  Ví dụ:
    [Lịch sử: Bot hỏi "Bạn muốn hỏi về sản phẩm nào?", trước đó user hỏi "cần hồ sơ gì"]
    "Vay mua ô tô" → "Hồ sơ cần chuẩn bị để vay mua ô tô tại Vietcombank là gì?"
    [Lịch sử: Bot hỏi làm rõ, trước đó user hỏi "điều kiện vay"]
    "Vay tín chấp CBNV" → "Điều kiện vay tín chấp CBNV tại Vietcombank là gì?"
    [Không tìm được câu hỏi gốc]
    "Vay xây mới cơ sở lưu trú du lịch" → "Vay xây mới cơ sở lưu trú du lịch tại Vietcombank là gì?"
  ❌ KHÔNG được dùng thông tin từ câu trả lời trước của bot để suy ra câu hỏi

---
BƯỚC 2 — QUY TẮC CHUNG (áp dụng cho cả 3 loại)

  - Chỉ trả về 1 câu hỏi duy nhất
  - Sửa lỗi chính tả tiếng Việt (bao gồm thiếu dấu: "alf" → "là", "dieu kien" → "điều kiện")
  - Không thêm bớt ý chính so với câu gốc
  - Tối ưu cho tìm kiếm tài liệu: đặt từ khóa quan trọng lên đầu khi có thể

---
Lịch sử hội thoại (từ cũ đến mới):
{history}

Câu hỏi hiện tại:
{query}

Câu hỏi đã viết lại:
"""
)


# -----------------------------
# Chain
# -----------------------------
rewrite_chain = (
    {
        "query": lambda x: x["query"],
        "history": history_formatter
    }
    | prompt
    | llm
    | StrOutputParser()
)