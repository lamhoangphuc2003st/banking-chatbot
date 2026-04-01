from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0
)

prompt = ChatPromptTemplate.from_template("""
Bạn là hệ thống phân loại intent chatbot ngân hàng Vietcombank.

Phân loại câu hỏi thành 3 loại:

CHAT
- chào hỏi
- cảm ơn
- nói chuyện xã giao

KNOWLEDGE
- thông tin chung về ngân hàng
- các dịch vụ, sản phẩm, gói vay, thẻ tín dụng, v.v.
- hướng dẫn sử dụng dịch vụ, sản phẩm
- chỉ cần có liên quan đến kiến thức ngân hàng

OUT_OF_SCOPE
- không liên quan ngân hàng

Chỉ trả về một từ:
CHAT / KNOWLEDGE / OUT_OF_SCOPE

Câu hỏi:
{query}
""")

chain = prompt | llm


def detect_intent(query):
    try:
        result = chain.invoke({"query": query})
        intent = result.content.strip().upper()

        valid = [
            "CHAT",
            "FAQ",
            "PRODUCT",
            "KNOWLEDGE",
            "OUT_OF_SCOPE"
        ]

        if intent not in valid:
            intent = "KNOWLEDGE"

        return intent

    except Exception:
        return "KNOWLEDGE"