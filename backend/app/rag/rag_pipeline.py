import os
import sys
import re
import json
import time
import logging
from logging.handlers import RotatingFileHandler
from typing import List, Dict
from openai import OpenAI
from dotenv import load_dotenv

from app.rag.hybrid_retriever import HybridRetriever
from app.rag.reranker import Reranker
from app.rag.query_rewriter import rewrite_query
from app.rag.multi_query import generate_queries

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -----------------------------
# Logging setup
# -----------------------------

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

LOG_DIR = os.path.join(BASE_DIR, "app", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger(__name__)
logger.propagate = False
logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)

file_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "rag.log"),
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8"
)
file_handler.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)


# -----------------------------
# Loan calculator
# -----------------------------
def loan_payment(principal, annual_rate, years):

    r = annual_rate / 12 / 100
    n = years * 12

    payment = principal * r * (1 + r) ** n / ((1 + r) ** n - 1)

    logger.info(
        f"Loan calculation: principal={principal}, rate={annual_rate}, years={years}, payment={payment}"
    )

    return round(payment, 2)


# -----------------------------
# Parse loan numbers
# -----------------------------
def extract_loan_info(query):

    q = query.lower()

    nums = list(map(float, re.findall(r"\d+", q)))

    if len(nums) < 3:
        return None

    principal = nums[0]
    years = nums[1]
    rate = nums[2]

    if "tỷ" in q:
        principal *= 1_000_000_000
    elif "triệu" in q:
        principal *= 1_000_000

    return principal, years, rate


# -----------------------------
# Intent classifier
# -----------------------------
def classify_intent(query: str):

    q = query.lower()

    if any(x in q for x in ["trả bao nhiêu", "mỗi tháng", "trả góp"]):
        return "loan_calculation"

    system_prompt = """
Bạn là bộ định tuyến intent cho chatbot ngân hàng.

Phân loại câu hỏi thành 3 loại:

1. info_query
   - hỏi thông tin, thắc mắc
   - điều kiện vay
   - đối tượng vay
   - loại khoản vay
   - lãi suất
   - thẻ tín dụng
   - hỏi cách giải quyết sự cố, khiếu nại phát sinh
   - dịch vụ ngân hàng

2. loan_calculation
   - yêu cầu tính toán khoản vay
   - có số tiền + lãi suất + thời gian
   - ví dụ:
     "Vay 500 triệu trong 10 năm lãi suất 8%"
     "Mỗi tháng trả bao nhiêu?"

3. out_of_scope
   - không liên quan đến ngân hàng, sản phẩm, dịch vụ
   - gian lận, hack
   - đầu tư crypto

Trả về JSON:

{"intent": "..."}
"""

    try:

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ]
        )

        text = response.choices[0].message.content.strip()

        data = json.loads(text)

        return data.get("intent", "info_query")

    except Exception as e:

        logger.error(f"Intent classification error: {e}")

        return "info_query"


class RAGPipeline:

    def __init__(self):

        logger.info("Initializing RAGPipeline")

        self.retriever = HybridRetriever()
        self.reranker = Reranker()

        self.max_multi_queries = 1
        self.retrieve_top_k = 15
        self.final_top_k = 15
        self.rerank_top_k = 5

        self.products = self.load_products()

    # -----------------------------
    # Load products
    # -----------------------------
    def load_products(self):

        base_dir = os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
        )

        data_path = os.path.join(
            base_dir,
            "data",
            "vietcombank_chunks.json"
        )

        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        products = set()

        for d in data:

            p = d.get("product_name")

            if p:
                products.add(p)

        products = list(products)

        logger.info(f"Loaded {len(products)} products")

        return products

    # -----------------------------
    # Product Router (LLM)
    # -----------------------------
    def detect_product(self, query):

        product_list = "\n".join(self.products)

        system_prompt = f"""
    Bạn là bộ định tuyến sản phẩm cho chatbot Vietcombank.

    Danh sách sản phẩm:

    {product_list}

    Kiểm tra câu hỏi có để cập đến sản phẩm nào trong danh sách sản phẩm không hoặc câu hỏi dạng yêu cầu liệt kê.

    Nếu trong câu hỏi có nhiều sản phẩm → trả nhiều.

    Nếu không có → null

    Trả JSON:

    {{"products":["product1","product2"]}}
    """

        try:

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ]
            )

            text = response.choices[0].message.content.strip()

            try:
                data = json.loads(text)
                products = data.get("products")

            except:
                logger.warning(f"Product router invalid JSON: {text}")
                return None

            if not products:
                return None

            logger.info(f"Product router detected: {products}")

            return products

        except Exception as e:

            logger.error(f"Product router error: {e}")

            return None

    # -----------------------------
    # Build context
    # -----------------------------
    def build_context(self, docs):

        context_parts = []

        for d in docs:

            text = d.get("text", "")

            if "Answer:" in text:

                parts = text.split("Answer:")

                q = parts[0].replace("Question:", "").strip()
                a = parts[1].strip()

            else:

                q = ""
                a = text

            block = f"""
Sản phẩm: {d.get("product_name","")}

Câu hỏi:
{q}

Câu trả lời:
{a}
"""

            context_parts.append(block.strip())

        return "\n\n".join(context_parts)

    # -----------------------------
    # Query processing
    # -----------------------------
    def generate_search_queries(self, query, history=None):

        # Rewrite query
        rewritten = rewrite_query(query, history)

        logger.info(f"Rewritten query: {rewritten}")

        # Detect product từ rewritten query
        products = self.detect_product(rewritten)

        logger.info(f"Detected products after rewrite: {products}")

        # Generate multi queries
        multi = generate_queries(
            rewritten,
            self.max_multi_queries
        )

        logger.info(f"Multi queries: {multi}")

        queries = list(dict.fromkeys([rewritten] + multi))

        if products:
            for p in products:
                queries.append(f"{rewritten} {p}")

        logger.info(f"Final search queries: {queries}")

        return queries, rewritten, products

    # -----------------------------
    # Retrieval
    # -----------------------------
    def retrieve_documents(self, queries, products=None):

        logger.info("Starting retrieval")

        all_results = []

        for q in queries:

            results = self.retriever.hybrid_search(
                q,
                top_k=self.retrieve_top_k
            )

            all_results.extend(results)

        merged = {}

        for r in all_results:

            key = r["doc_id"]

            if key not in merged:
                merged[key] = r
            else:
                merged[key]["score"] = max(
                    merged[key]["score"],
                    r["score"]
                )

        docs = list(merged.values())

        if products:

            filtered = []

            for d in docs:

                name = (d.get("product_name") or "").lower()

                for p in products:

                    if p.lower() in name:
                        filtered.append(d)
                        break

            if filtered:
                docs = filtered
            else:
                logger.warning("Product filter empty → fallback")

        docs = sorted(
            docs,
            key=lambda x: x["score"],
            reverse=True
        )[:self.final_top_k]

        logger.info(f"Retrieved docs: {len(docs)}")

        return docs

    # -----------------------------
    # RAG answer
    # -----------------------------
    def rag_answer(self, query, history=None):

        start_time = time.time()

        queries, rewritten, products = self.generate_search_queries(
            query,
            history
        )

        retrieved = self.retrieve_documents(
            queries,
            products
        )

        if not retrieved:
            return "Tôi không tìm thấy thông tin."

        reranked = self.reranker.rerank(
            rewritten,
            retrieved,
            top_k=self.rerank_top_k
        )

        context = self.build_context(reranked)

        system_prompt = """
Bạn là chuyên gia tư vấn Vietcombank.
Trả lời dựa trên thông tin cung cấp.
"""

        user_prompt = f"""
Thông tin:

{context}

Câu hỏi:
{query}
"""

        try:

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )

            answer = response.choices[0].message.content

        except Exception as e:

            logger.error(f"LLM error: {e}")

            return "Hệ thống đang gặp lỗi."

        latency = time.time() - start_time

        logger.info(f"RAG latency: {latency:.2f}s")

        return answer

    # -----------------------------
    # Main ask
    # -----------------------------
    def ask(self, query, history=None):

        logger.info(f"User request: {query}")

        intent = classify_intent(query)

        if intent == "loan_calculation":

            loan_info = extract_loan_info(query)

            if loan_info:

                principal, years, rate = loan_info

                payment = loan_payment(
                    principal,
                    rate,
                    years
                )

                return f"Mỗi tháng bạn cần trả khoảng {payment:,.0f} VND."

            return "Không đủ thông tin để tính khoản vay."

        elif intent == "info_query":

            return self.rag_answer(query, history)

        else:

            return "Xin lỗi, tôi không thể hỗ trợ yêu cầu này."