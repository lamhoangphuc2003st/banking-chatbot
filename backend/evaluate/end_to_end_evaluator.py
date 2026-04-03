# evaluate/end_to_end_evaluator.py
import asyncio
import json
import time
from dotenv import load_dotenv
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# Import pipeline của bạn
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from app.rag.pipeline import RAGPipeline

load_dotenv()

# -------------------------------------------------------
# Judge prompt
# -------------------------------------------------------
JUDGE_PROMPT = ChatPromptTemplate.from_template("""
Bạn là chuyên gia đánh giá chất lượng chatbot ngân hàng Vietcombank.
Đánh giá câu trả lời dựa trên câu hỏi và ngữ cảnh.

Câu hỏi: {query}
Câu trả lời của bot: {answer}
Thông tin tham khảo (nếu có): {reference}

Chấm điểm từng tiêu chí (1-5):

1. faithfulness (trung thực): Câu trả lời có bịa thông tin không có trong tài liệu không?
   5 = hoàn toàn dựa trên tài liệu
   1 = nhiều thông tin bịa đặt

2. relevance (liên quan): Câu trả lời có trả lời đúng câu hỏi không?
   5 = trả lời trực tiếp và đầy đủ
   1 = không liên quan đến câu hỏi

3. completeness (đầy đủ): Câu trả lời có bao gồm đủ thông tin quan trọng không?
   5 = đầy đủ tất cả thông tin cần thiết
   1 = thiếu nhiều thông tin quan trọng

4. clarity (rõ ràng): Câu trả lời có dễ đọc, dễ hiểu không?
   5 = rất rõ ràng, có cấu trúc tốt
   1 = khó hiểu, lộn xộn

Trả về JSON (không markdown):
{{"faithfulness": X, "relevance": X, "completeness": X, "clarity": X,
  "overall": X, "reason": "giải thích ngắn gọn"}}
""")


@dataclass
class EvalResult:
    case_id: str
    category: str
    query: str
    rewritten_query: str
    answer: str
    latency_ms: int
    retrieval_latency_ms: int
    # Behavior check
    behavior_correct: bool
    behavior_expected: str
    behavior_actual: str
    # Content check
    contains_check: bool
    missing_keywords: list
    forbidden_keywords: list
    # LLM judge scores
    faithfulness: Optional[float] = None
    relevance: Optional[float] = None
    completeness: Optional[float] = None
    clarity: Optional[float] = None
    overall: Optional[float] = None
    judge_reason: Optional[str] = None
    # Error
    error: Optional[str] = None


class EndToEndEvaluator:
    def __init__(self):
        self.pipeline = RAGPipeline()
        self.judge_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.judge_chain = JUDGE_PROMPT | self.judge_llm

    async def run_pipeline(self, query: str, history: list = None) -> dict:
        """Chạy pipeline và thu thập full response + metadata."""
        tokens = []
        metadata = {}
        start = time.time()

        try:
            async for token in self.pipeline.stream(
                query=query,
                history=history or [],
            ):
                tokens.append(token)

            answer = "".join(tokens)
            latency_ms = int((time.time() - start) * 1000)

            return {
                "answer": answer,
                "latency_ms": latency_ms,
                "error": None,
            }
        except Exception as e:
            return {
                "answer": "",
                "latency_ms": int((time.time() - start) * 1000),
                "error": str(e),
            }

    def check_behavior(self, answer: str, expected_behavior: str) -> tuple[bool, str]:
        """Detect actual behavior từ câu trả lời."""
        answer_lower = answer.lower()

        CLARIFY_SIGNALS = ["bạn muốn hỏi về sản phẩm", "sản phẩm nào", "dịch vụ nào"]
        OOS_SIGNALS = ["chỉ hỗ trợ", "ngoài phạm vi", "không hỗ trợ thông tin"]
        CHAT_SIGNALS = ["xin chào", "chào bạn", "tôi có thể giúp gì"]

        if any(s in answer_lower for s in CLARIFY_SIGNALS):
            actual = "clarification"
        elif any(s in answer_lower for s in OOS_SIGNALS):
            actual = "out_of_scope"
        elif any(s in answer_lower for s in CHAT_SIGNALS) and len(answer) < 100:
            actual = "chat"
        else:
            actual = "knowledge"

        return actual == expected_behavior, actual

    def check_content(self, answer: str, case: dict) -> tuple[bool, list, list]:
        """Kiểm tra expected_contains và expected_not_contains."""
        answer_lower = answer.lower()
        missing = []
        forbidden = []

        for keyword in case.get("expected_contains", []):
            if keyword.lower() not in answer_lower:
                missing.append(keyword)

        for keyword in case.get("expected_not_contains", []):
            if keyword.lower() in answer_lower:
                forbidden.append(keyword)

        passed = not missing and not forbidden
        return passed, missing, forbidden

    async def judge_answer(self, query: str, answer: str, reference: str = "") -> dict:
        """LLM judge đánh giá chất lượng câu trả lời."""
        if not answer or len(answer) < 10:
            return {"faithfulness": 1, "relevance": 1, "completeness": 1,
                    "clarity": 1, "overall": 1, "reason": "Empty answer"}
        try:
            response = await self.judge_chain.ainvoke({
                "query": query,
                "answer": answer,
                "reference": reference or "Không có"
            })
            text = response.content.strip()
            return json.loads(text)
        except Exception as e:
            return {"error": str(e)}

    async def evaluate_case(self, case: dict) -> EvalResult:
        """Evaluate một test case."""
        print(f"  [{case['id']}] {case['query'][:50]}...")

        history = case.get("history", [])
        expected_behavior = case.get("expected_behavior", "knowledge")

        # Run pipeline
        result = await self.run_pipeline(case["query"], history)
        answer = result["answer"]

        # Check behavior
        behavior_correct, actual_behavior = self.check_behavior(answer, expected_behavior)

        # Check content (chỉ khi behavior đúng)
        if behavior_correct and expected_behavior == "knowledge":
            contains_ok, missing, forbidden = self.check_content(answer, case)
        else:
            contains_ok = behavior_correct
            missing, forbidden = [], []

        # LLM judge (chỉ cho knowledge responses)
        judge_scores = {}
        if expected_behavior == "knowledge" and answer:
            reference = case.get("ground_truth", "")
            judge_scores = await self.judge_answer(case["query"], answer, reference)

        return EvalResult(
            case_id=case["id"],
            category=case.get("category", "unknown"),
            query=case["query"],
            rewritten_query="",  # lấy từ log nếu cần
            answer=answer,
            latency_ms=result["latency_ms"],
            retrieval_latency_ms=0,
            behavior_correct=behavior_correct,
            behavior_expected=expected_behavior,
            behavior_actual=actual_behavior,
            contains_check=contains_ok,
            missing_keywords=missing,
            forbidden_keywords=forbidden,
            faithfulness=judge_scores.get("faithfulness"),
            relevance=judge_scores.get("relevance"),
            completeness=judge_scores.get("completeness"),
            clarity=judge_scores.get("clarity"),
            overall=judge_scores.get("overall"),
            judge_reason=judge_scores.get("reason"),
            error=result["error"],
        )

    async def evaluate_all(self, test_cases: list[dict]) -> list[EvalResult]:
        results = []
        for i, case in enumerate(test_cases, 1):
            print(f"[{i}/{len(test_cases)}]", end=" ")
            result = await self.evaluate_case(case)
            results.append(result)
            await asyncio.sleep(0.5)  # tránh rate limit
        return results


def print_report(results: list[EvalResult]):
    total = len(results)
    errors = [r for r in results if r.error]
    behavior_ok = [r for r in results if r.behavior_correct]
    content_ok = [r for r in results if r.contains_check]

    knowledge_results = [r for r in results
                         if r.behavior_expected == "knowledge" and r.faithfulness is not None]

    print("\n" + "=" * 60)
    print("  END-TO-END EVALUATION REPORT")
    print("=" * 60)
    print(f"  Total cases    : {total}")
    print(f"  Errors         : {len(errors)}")
    print(f"  Behavior pass  : {len(behavior_ok)}/{total} ({len(behavior_ok)/total*100:.1f}%)")
    print(f"  Content pass   : {len(content_ok)}/{total} ({len(content_ok)/total*100:.1f}%)")

    if knowledge_results:
        def avg(metric):
            vals = [getattr(r, metric) for r in knowledge_results
                    if getattr(r, metric) is not None]
            return sum(vals) / len(vals) if vals else 0

        print(f"\n  LLM Judge Scores (avg, scale 1-5):")
        print(f"    Faithfulness  : {avg('faithfulness'):.2f}")
        print(f"    Relevance     : {avg('relevance'):.2f}")
        print(f"    Completeness  : {avg('completeness'):.2f}")
        print(f"    Clarity       : {avg('clarity'):.2f}")
        print(f"    Overall       : {avg('overall'):.2f}")

async def main():
    here = Path(__file__).parent
    dataset_file = here / "golden_dataset.json"

    with open(dataset_file, encoding="utf-8") as f:
        test_cases = json.load(f)

    print(f"Evaluating {len(test_cases)} cases...")
    evaluator = EndToEndEvaluator()
    results = await evaluator.evaluate_all(test_cases)

    print_report(results)

    # Save results
    with open(here / "e2e_results.json", "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in results], f, ensure_ascii=False, indent=2)
    print("\nSaved: e2e_results.json")


if __name__ == "__main__":
    asyncio.run(main())