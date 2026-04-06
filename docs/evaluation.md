# Evaluation Guide

## 1. Retrieval Evaluation

Đánh giá khả năng tìm đúng tài liệu cho 227 chunks.

```bash
cd backend
python evaluate/evaluate_retrieval.py
```

**Metrics:**
- **Hit Rate @k=15**: % câu hỏi có doc đúng trong top-15
- **MRR**: Mean Reciprocal Rank

**Target:** Hit Rate > 80%, MRR > 0.6

---

## 2. End-to-End Evaluation

Đánh giá chất lượng câu trả lời với LLM-as-judge.

```bash
python evaluate/end_to_end_evaluator.py
```

**Metrics (1-5):**
- **Faithfulness**: Câu trả lời có bịa thông tin không?
- **Relevance**: Có trả lời đúng câu hỏi không?
- **Completeness**: Có đủ thông tin không?
- **Clarity**: Có rõ ràng không?

---

## 3. Latency Analysis

```bash
python scripts/analyze_latency.py --days 7
python scripts/analyze_latency.py --hours 24
```

**Target latency:**

| Path | P50 | P95 |
|---|---|---|
| Redis hit | < 2s | < 3.5s |
| Semantic hit | < 3s | < 5s |
| Cache miss | < 6s | < 10s |
| Decompose | < 8s | < 14s |

---

## 4. Load Testing

```bash
# Web UI
locust -f locustfile.py --host=http://localhost:8000

# Headless — từng scenario
make load-baseline   # 5 users
make load-normal     # 20 users
make load-peak       # 50 users
make load-stress     # 100 users

# So sánh kết quả
make load-compare
```

**Lưu ý:** `/chat` là streaming endpoint — Locust mặc định đo TTFT.
File `locustfile.py` đã fix để đo total response time qua metric `/chat [total]`.

---

## 5. Kết quả hiện tại

### Retrieval (227 test cases)

| Section | Hit Rate |
|---|---|
| list | ~100% |
| Thông tin chung | ~75% |
| Hồ sơ chuẩn bị | ~80% |
| QA pairs | ~70% |
| condition (thẻ) | ~90% |
| fee (thẻ) | ~85% |

### Latency (production logs)

| Path | P50 | P95 |
|---|---|---|
| Redis hit | ~2s | ~4s |
| Semantic hit | ~3s | ~6s |
| Cache miss | ~6-8s | ~10-12s |
