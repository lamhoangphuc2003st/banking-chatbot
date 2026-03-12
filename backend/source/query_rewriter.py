from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def rewrite_query(query: str, history=None) -> str:

    if not history:

        prompt = f"""
Bạn là hệ thống rewrite query cho tìm kiếm tài liệu ngân hàng Vietcombank.

Nhiệm vụ:
- Viết lại câu hỏi rõ ràng hơn
- Giữ nguyên ý nghĩa
- Tối ưu cho tìm kiếm tài liệu ngân hàng

Chỉ trả về 1 câu hỏi duy nhất.

Câu hỏi:
{query}
"""

    else:

        history_text = ""

        for h in history[-5:]:

            role = "Người dùng" if h["role"] == "user" else "Trợ lý"

            history_text += f"{role}: {h['content']}\n"

        prompt = f"""
Bạn là hệ thống rewrite query cho chatbot ngân hàng Vietcombank.

Dựa trên lịch sử hội thoại, hãy viết lại câu hỏi cuối cùng
thành câu hỏi đầy đủ và rõ nghĩa.

Quy tắc:
- Giữ nguyên ý nghĩa
- Nếu câu hỏi thiếu tên sản phẩm cần hỏi thì bổ sung từ lịch sử gần nhất
- Tối ưu cho tìm kiếm tài liệu
- Chỉ trả về 1 câu hỏi

Lịch sử hội thoại:
{history_text}

Câu hỏi hiện tại:
{query}
"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )

    rewritten = resp.choices[0].message.content.strip()

    return rewritten