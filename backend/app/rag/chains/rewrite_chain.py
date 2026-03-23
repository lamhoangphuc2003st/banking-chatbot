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

    for h in history[-5:]:  # dùng 5 message gần nhất

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

Dựa trên lịch sử hội thoại, hãy viết lại câu hỏi cuối cùng thành câu hỏi đầy đủ và rõ nghĩa.

Quy tắc:
- Giữ nguyên ý chính của câu hỏi, không được thêm bớt ý chính
- Nếu câu hỏi tham chiếu mơ hồ như:
  - "gói trên"
  - "4 gói trên"
  - "các sản phẩm này"
  - "những gói vay đó"
  - "các khoản vay trên"
  => PHẢI thay bằng tên sản phẩm cụ thể từ lịch sử hội thoại gần nhất của bạn và người dùng
- Tối ưu cho tìm kiếm tài liệu
- Chỉ trả về 1 câu hỏi

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