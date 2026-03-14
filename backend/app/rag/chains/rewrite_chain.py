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
Bạn là hệ thống rewrite query cho chatbot Vietcombank.

Nhiệm vụ:
- Viết lại câu hỏi rõ ràng hơn
- Sử dụng lịch sử hội thoại gần nhất để xác định nếu thiếu thông tin cần thiết cho câu hỏi
- Giữ nguyên ý nghĩa
- Tối ưu cho tìm kiếm tài liệu ngân hàng

Quy tắc:
- Chỉ trả về 1 câu hỏi
- Không giải thích

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