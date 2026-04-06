from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.rag.utils.llm_client import llm

prompt = ChatPromptTemplate.from_template("""
Bạn là hệ thống tách câu hỏi cho chatbot ngân hàng Vietcombank.

Nếu câu hỏi chứa nhiều ý → tách thành nhiều câu hỏi độc lập.
Nếu chỉ có 1 ý → giữ nguyên.

Quy tắc:
- mỗi câu hỏi độc lập
- rõ nghĩa
- tối ưu cho search
- KHÔNG paraphrase dài dòng
- trả về JSON list

Query:
{query}
""")

decompose_chain = (
    prompt
    | llm
    | JsonOutputParser()
)