from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.2
)

prompt = ChatPromptTemplate.from_template(
"""
Tạo 1 truy vấn tìm kiếm khác cùng ý nghĩa.

Chỉ trả về truy vấn.
Không giải thích.

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