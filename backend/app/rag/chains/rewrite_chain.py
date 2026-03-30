from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda


llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0
)


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

Nhiệm vụ: Viết lại câu hỏi thành câu đầy đủ, rõ nghĩa, tối ưu cho tìm kiếm tài liệu.

---

QUY TẮC QUAN TRỌNG — Phân biệt 2 loại câu hỏi:

[LOẠI 1] Câu có THAM CHIẾU MƠ HỒ đến sản phẩm đã nhắc trước đó
- Dấu hiệu: chứa "gói đó", "sản phẩm trên", "4 gói trên", "cái đó", "các gói này", "những sản phẩm trên"...
- Hành động: PHẢI tra lịch sử và thay bằng các gói sản phẩm được liệt kê ra đến gần nhất
- Ví dụ:
  + "gói đó phí bao nhiêu" → "Phí của [Tên sản phẩm cụ thể từ lịch sử] là bao nhiêu?"
  + "4 gói trên điều kiện như thế nào" → "Điều kiện vay của [SP1], [SP2], [SP3], [SP4] là gì?"

[LOẠI 2] Câu THIẾU ĐỐI TƯỢNG — không nhắc đến sản phẩm nào, kể cả trong lịch sử
- Dấu hiệu: hỏi điều kiện/phí/lãi suất/thủ tục... mà KHÔNG có tên sản phẩm cụ thể
- Hành động: GIỮ NGUYÊN ý, chỉ sửa lỗi chính tả và chuẩn hóa — KHÔNG được tự thêm tên sản phẩm
- Ví dụ:
  + "điều kiện vay là gì" → "Điều kiện vay tại Vietcombank là gì?"  (KHÔNG thêm tên gói)
  + "phí là bao nhiêu" → "Phí tại Vietcombank là bao nhiêu?"  (KHÔNG thêm tên sản phẩm)
  + "Đieu kien vay la gi" → "Điều kiện vay tại Vietcombank là gì?"  (chỉ sửa lỗi chính tả)

---

Quy tắc chung:
- Chỉ trả về 1 câu hỏi duy nhất
- Không thêm bớt ý chính
- Tối ưu cho tìm kiếm tài liệu

---

Lịch sử hội thoại:
{history}

Câu hỏi hiện tại:
{query}
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