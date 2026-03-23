from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import json
import re


llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0
)

prompt = ChatPromptTemplate.from_template("""
Bạn là bộ định tuyến sản phẩm cho chatbot Vietcombank.

Danh sách sản phẩm:
{products}

Nhiệm vụ:
Kiểm tra câu hỏi có thể liên quan đến sản phẩm nào trong danh sách không.

QUY TẮC QUAN TRỌNG:

1. Nếu câu hỏi mang tính LIỆT KÊ / TỔNG HỢP 
(ví dụ: "có những loại nào", "các gói vay gì", "bao nhiêu loại"...)
→ trả []

2. Nếu câu hỏi có dạng:
- "ngoài ... còn ..."
- "khác ..."
- "còn gói nào"
- "thêm gói nào"
- "những gói nào khác"
→ đây là câu hỏi LIỆT KÊ
→ trả []

3. Nếu câu hỏi KHÔNG nhắc đến sản phẩm cụ thể
→ trả []

4. Chỉ khi user hỏi trực tiếp về sản phẩm cụ thể
→ trả về đúng tên sản phẩm trong danh sách


Chỉ trả về JSON list, không thêm bất kỳ văn bản nào khác.

Format:
["product1","product2"]

---

Ví dụ:

Câu hỏi: Vietcombank có những gói vay nào?
Output:
[]

Câu hỏi: Có những thẻ tín dụng nào của Vietcombank?
Output:
[]

Câu hỏi: Ngoài gói vay An tâm kinh doanh, còn gói nào khác?
Output:
[]
                                          
Câu hỏi: Tôi muốn vay mua ô tô
Output:
["Vay mua ô tô"]

Câu hỏi: Lợi ích của thẻ Vietcombank Vibe Platinum là gì?
Output:
["Vietcombank Vibe Platinum"]

Câu hỏi: Các đặc quyền khi mở thẻ Vibe Platinum
Output:
["Vietcombank Vibe Platinum"]

---

Câu hỏi:
{query}

JSON:
""")


chain = prompt | llm


def detect_product(query, products):

    response = chain.invoke({
        "query": query,
        "products": ", ".join(products)
    })

    text = response.content.strip()

    # extract JSON nếu LLM trả thêm text
    match = re.search(r"\[.*?\]", text)

    if match:
        text = match.group()

    try:
        result = json.loads(text)
    except:
        result = []

    return result