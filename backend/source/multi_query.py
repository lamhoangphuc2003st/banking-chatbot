from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_queries(query: str, n_queries: int = 3):

    prompt = f"""
Bạn là hệ thống tạo nhiều truy vấn tìm kiếm cho chatbot ngân hàng.

Từ câu hỏi của người dùng, hãy tạo {n_queries} câu hỏi khác nhau
nhưng cùng ý nghĩa để tìm kiếm tài liệu.

Chỉ trả về danh sách câu hỏi, mỗi câu một dòng.

Câu hỏi:
{query}
"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )

    text = resp.choices[0].message.content

    queries = [q.strip("- ").strip() for q in text.split("\n") if q.strip()]

    return queries[:n_queries]