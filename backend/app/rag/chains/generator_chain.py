from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0
)

prompt = ChatPromptTemplate.from_template(
"""
Bạn là chuyên gia tư vấn Vietcombank.

Sử dụng thông tin được cung cấp để trả lời ý chính cho câu hỏi.

Sử dụng markdown heading và bullet để format câu trả lời.

Khi không có thông tin liên quan thì mới trả lời:
"Tôi không tìm thấy thông tin" và hướng dẫn khách hàng liên hệ tổng đài.

Context:
{context}

Question:
{question}
"""
)

generator_chain = prompt | llm