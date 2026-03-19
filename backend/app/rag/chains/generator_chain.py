from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2
)

prompt = ChatPromptTemplate.from_template(
"""
Bạn là chuyên gia tư vấn Vietcombank.

Chỉ sử dụng thông tin trong Context để trả lời.
Nếu Context có thông tin liên quan, hãy trả lời đầy đủ và rõ ràng.

Chỉ khi Context hoàn toàn không chứa thông tin liên quan thì mới trả lời:
"Tôi không tìm thấy thông tin" và hướng dẫn khách hàng liên hệ tổng đài.

Context:
{context}

Question:
{question}
"""
)

generator_chain = prompt | llm