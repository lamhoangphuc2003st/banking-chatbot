from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0
)

prompt = ChatPromptTemplate.from_template(
"""
Bạn là chuyên gia tư vấn Vietcombank.

Sử dụng thông tin được cung cấp trong Context để trả lời cho câu hỏi.

Yêu cầu: Không được rút gọn nội dung, không được thêm thông tin ngoài Context, chỉ trả lời dựa trên thông tin trong Context.

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