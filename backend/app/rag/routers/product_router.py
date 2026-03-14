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
Xác định khách hàng đang hỏi về sản phẩm nào trong danh sách.

Nếu câu hỏi liên quan nhiều sản phẩm → trả nhiều.

Chỉ trả về JSON list, không thêm bất kỳ văn bản nào khác.

Format:
["product1","product2"]

Nếu không có sản phẩm nào phù hợp thì trả về:
[]

Ví dụ:

Câu hỏi: tôi muốn vay mua xe
Output:
["Vay mua ô tô"]

Câu hỏi: mở thẻ visa cần điều kiện gì
Output:
["Thẻ tín dụng"]

Câu hỏi: lãi suất gửi tiết kiệm là bao nhiêu
Output:
["Tiết kiệm"]

Câu hỏi: vay mua nhà và vay mua xe khác gì nhau
Output:
["Vay mua nhà","Vay mua ô tô"]

Bây giờ hãy phân loại câu hỏi sau.

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

    return result or None