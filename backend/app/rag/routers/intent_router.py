from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0
)

prompt = ChatPromptTemplate.from_template("""
Bạn là hệ thống phân loại intent cho chatbot ngân hàng Vietcombank.

Phân loại câu hỏi thành 2 loại:

CHAT
- chào hỏi
- cảm ơn
- hỏi chatbot là ai
- nói chuyện chung

KNOWLEDGE
- hỏi về sản phẩm Vietcombank
- hỏi phí
- hỏi lãi suất
- hỏi điều kiện mở thẻ
- hỏi thông tin dịch vụ

Chỉ trả về một từ:
CHAT hoặc KNOWLEDGE

Câu hỏi:
{query}
""")

chain = prompt | llm


def detect_intent(query):

    try:

        result = chain.invoke({
            "query": query
        })

        intent = result.content.strip().upper().replace(".", "")

        if intent not in ["CHAT", "KNOWLEDGE"]:
            intent = "KNOWLEDGE"

        return intent

    except Exception:
        return "KNOWLEDGE"