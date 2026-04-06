# Vietcombank RAG Chatbot

Chatbot hỗ trợ khách hàng tra cứu thông tin **sản phẩm vay và thẻ tín dụng** của ngân hàng Vietcombank, xây dựng trên kiến trúc **Retrieval-Augmented Generation (RAG)** với các tối ưu hóa async end-to-end.

> **Phạm vi dữ liệu:** Vay mua ô tô, vay bất động sản, vay tiêu dùng, vay sản xuất kinh doanh và 13 loại thẻ tín dụng Vietcombank.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-latest-green)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-orange)
![Qdrant](https://img.shields.io/badge/Qdrant-Cloud-red)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Phạm vi hỗ trợ

Chatbot có thể trả lời các câu hỏi về:

**Sản phẩm vay:**
- Vay mua ô tô
- Vay nhu cầu bất động sản (Vay xây sửa nhà ở, Nhà Mới Thành Đạt, Vay mua nhà dự án, Vay mua nhà ở đất ở)
- Vay sản xuất kinh doanh (An tâm kinh doanh, Kinh doanh tài lộc, Vay xây mới / nâng cấp cơ sở lưu trú du lịch)
- Vay tiêu dùng (Vay tín chấp theo lương, Vay cầm cố giấy tờ có giá, Vay tiêu dùng có tài sản bảo đảm)

**Thẻ tín dụng (13 loại):**
- Vietcombank Vibe Platinum, Vietcombank Cashplus Platinum American Express®, Vietcombank Mastercard® World, Vietcombank Visa Platinum
- Vietcombank Vietnam Airlines Platinum American Express®, Vietcombank JCB Platinum, Vietcombank Vibe, Vietcombank Vietnam Airlines American Express®
- Vietcombank JCB, Vietcombank American Express®, Vietcombank Mastercard®, Vietcombank Visa Snack, Saigon Centre Takashimaya Vietcombank

**Thông tin hỗ trợ:** điều kiện, đối tượng khách hàng, hồ sơ cần chuẩn bị, biểu phí, quy trình vay, ngày trả nợ, thông tin thẻ, lợi ích thẻ, điều kiện mở thẻ, biểu phí thẻ.

> ⚠️ Chatbot **không hỗ trợ** giao dịch trực tiếp, tra cứu số dư tài khoản, hoặc các sản phẩm ngoài danh sách trên.

---

## Kiến trúc hệ thống

```
                      User Query
                          │
                          ▼
┌─────────────────────────────────────────────────────┐
│                    FastAPI API Layer                │
└─────────────────────────┬───────────────────────────┘
                          │
            ┌─────────────▼─────────────┐
            │        RAG Pipeline       │
            │  ┌────────┐ ┌──────────┐  │
            │  │Rewrite │ │ Clarify  │  │  ← Song song
            │  └────────┘ └──────────┘  │
            │  ┌────────┐ ┌──────────┐  │
            │  │Intent  │ │  Redis   │  │  ← Song song
            │  │Router  │ │  Cache   │  │
            │  └────────┘ └──────────┘  │
            │  ┌────────────────────┐   │
            │  │  Semantic Cache    │   │  ← Qdrant faq_cache
            │  └────────────────────┘   │
            │  ┌────────────────────┐   │
            │  │ Retrieve → Rerank  │   │  ← Qdrant + Cohere
            │  │ → Compress → LLM   │   │
            │  └────────────────────┘   │
            └───────────────────────────┘
```

### Tech Stack

| Component | Technology |
|---|---|
| API Framework | FastAPI + Uvicorn |
| LLM | OpenAI GPT-4o-mini |
| Vector DB | Qdrant Cloud |
| Reranker | Cohere rerank-v3.5 |
| Cache L1 | Redis (exact match) |
| Cache L2 | Qdrant semantic search |
| Embedding | OpenAI text-embedding-3-large |
| Deployment | Render (backend) + Vercel (frontend) |

---

## Tính năng nổi bật

### Pipeline tối ưu async

- **Bước 1**: Rewrite + Clarify check chạy song song — tiết kiệm ~1s so với tuần tự
- **Bước 2**: Intent detection + Redis cache + Embedding chạy song song — embed sớm, dùng lại cho cả semantic cache và retrieve
- **Decompose task** bắt đầu ngay sau rewrite, chạy ngầm trong khi cache check — tiết kiệm thêm ~1s khi cache miss
- Cache write là **fire-and-forget** — không block user response

### Dual-layer caching

- **L1 — Redis**: exact match trên rewritten query, hit trong ~50ms
- **L2 — Qdrant Semantic**: cosine similarity ≥ 0.92, tái dùng embedding đã tính — không re-embed
- Cache hit rate trung bình: **~60–70%** sau warm-up

### Decompose pipeline

Query phức tạp (chứa "và", "hoặc", nhiều sản phẩm) tự động tách thành sub-queries. Mỗi sub-query có cache riêng, chạy song song qua `asyncio.gather`, kết quả merge lại trước khi generate.

### Hybrid clarification

- **Layer 1 (Rule-based)**: phát hiện query mơ hồ không tốn token
- **Layer 2 (LLM)**: chỉ gọi khi cần, extract sản phẩm từ history để gợi ý chính xác
- Tự động bỏ qua khi user đang trả lời câu hỏi clarification

---

## Kết quả đánh giá

| Metric | Value |
|---|---|
| Retrieval Hit Rate (k=15) | ~85% |
| Cache hit rate | ~65% |
| P50 latency — cache hit | ~2s |
| P50 latency — cache miss | ~6s |
| P95 latency — cache miss | ~10s |

---

## Cài đặt

### Yêu cầu

- Python 3.11+
- Redis instance
- Qdrant Cloud account
- OpenAI API key
- Cohere API key

### 1. Clone repo

```bash
git clone https://github.com/lamhoangphuc2003st/banking-chatbot.git
cd banking-chatbot
```

### 2. Tạo virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows
```

### 3. Cài dependencies

```bash
pip install -r backend/requirements.txt
```

### 4. Cấu hình environment

```bash
cp backend/.env.example backend/.env
# Điền các giá trị API keys vào .env
```

### 5. Khởi tạo database

```bash
cd backend
python app/database/init_db.py
```

### 6. Ingest dữ liệu vào Qdrant

```bash
cd backend
python vectorstore/ingest_qdrant.py
```

### 7. Chạy server

```bash
cd backend
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

### 8. Chạy frontend

```bash
cd frontend
npm install
npm start
```

---

## Cấu trúc dự án

```
bank-chatbot/
├── backend/
│   ├── app/
│   │   ├── database/              # Database logging & migrations
│   │   │   ├── migrations/
│   │   │   ├── connection.py
│   │   │   ├── database_logger.py
│   │   │   └── init_db.py
│   │   └── rag/
│   │       ├── cache/             # Redis + Semantic cache
│   │       ├── chains/            # LangChain chains (rewrite, decompose, clarify...)
│   │       ├── retrieval/         # Qdrant retriever, reranker, compressor
│   │       ├── routers/           # Intent routing
│   │       ├── utils/             # Logger, latency tracker, LLM client
│   │       └── pipeline.py        # Main RAG pipeline
│   ├── evaluate/                  # Evaluation scripts & golden dataset
│   ├── scripts/                   # Latency analysis & load testing
│   ├── vectorstore/               # Data ingestion
│   ├── api.py                     # FastAPI entrypoint
│   ├── locustfile.py              # Load testing
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── crawler/                       # Data crawling & normalization
│   ├── raw/                       # Raw scraped data
│   ├── normalizer/                # Data normalization scripts
│   └── chunk/                     # Chunking scripts
├── frontend/                      # Frontend application
└── docs/
    ├── architecture.md
    ├── api.md
    └── evaluation.md
```

---

## API Reference

### `POST /chat`

Gửi tin nhắn và nhận stream response.

**Request:**
```json
{
  "messages": [
    {"role": "user", "content": "VCB có cho vay tiêu dùng không?"}
  ],
  "session_id": "optional-uuid"
}
```

**Response:** `text/event-stream` — stream từng token

### `GET /health`

```json
{"status": "ok"}
```

---

## Evaluation

```bash
# Đánh giá retrieval (227 test cases)
cd backend
python evaluate/evaluate_retrieval.py

# Đánh giá end-to-end (LLM-as-judge)
python evaluate/end_to_end_evaluator.py

# Phân tích latency từ production logs
python scripts/analyze_latency.py --days 7
```

## Load Testing

```bash
pip install locust

# Web UI
locust -f locustfile.py --host=http://localhost:8000

# Headless
locust -f locustfile.py --host=http://localhost:8000 \
  --users=20 --spawn-rate=2 --run-time=5m --headless --csv=results/normal
```

---

## Deployment

### Docker

```bash
cd backend
docker build -t bank-chatbot .
docker run -p 8000:8000 --env-file .env bank-chatbot
```

### Render

- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn api:app --host 0.0.0.0 --port $PORT`

---

## Đóng góp

1. Fork repo
2. Tạo branch: `git checkout -b feature/ten-tinh-nang`
3. Commit: `git commit -m 'feat: mô tả thay đổi'`
4. Push: `git push origin feature/ten-tinh-nang`
5. Tạo Pull Request

---

## License

MIT License — xem [LICENSE](LICENSE) để biết thêm chi tiết.