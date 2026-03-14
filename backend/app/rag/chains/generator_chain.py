from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2
)

prompt = ChatPromptTemplate.from_template(
"""
Bạn là chuyên gia tư vấn Vietcombank.
Trả lời dựa trên thông tin cung cấp và đúng ý nghĩa câu hỏi.
Nếu không có thông tin hãy trả lời không có, không được tự bịa thông tin.

Context:
{context}

Question:
{question}
"""
)

generator_chain = prompt | llm