from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0
)

prompt = ChatPromptTemplate.from_template(
"""
Bạn là hệ thống tạo nhiều truy vấn tìm kiếm cho chatbot ngân hàng.

Từ câu hỏi của người dùng, hãy tạo thêm 1 câu hỏi khác nhưng cùng ý nghĩa để tìm kiếm tài liệu.

Chỉ trả về câu hỏi.

Query:
{query}
"""
)

def parse(text):

    return [
        q.strip("- ").strip()
        for q in text.split("\n")
        if q.strip()
    ]

multi_query_chain = (
    prompt
    | llm
    | StrOutputParser()
    | RunnableLambda(parse)
)