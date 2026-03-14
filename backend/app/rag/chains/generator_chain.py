from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2
)

prompt = ChatPromptTemplate.from_template(
"""
Bạn là chuyên gia tư vấn Vietcombank.
Trả lời dựa trên thông tin cung cấp.
Nếu không có thông tin, hãy trả lời ""Tôi không tìm thấy thông tin" và hướng dẫn khách hàng liên hệ tổng đài 1900 54 54 13 hoặc đến chi nhánh gần nhất để được hỗ trợ.

Context:
{context}

Question:
{question}

"""
)

generator_chain = prompt | llm