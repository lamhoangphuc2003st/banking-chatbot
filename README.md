# Vietcombank RAG Chatbot

Hệ thống chatbot hỗ trợ khách hàng ngân hàng Vietcombank, xây dựng trên kiến trúc **Retrieval-Augmented Generation (RAG)** với các tối ưu hóa async end-to-end.

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
| Deployment | Render / Docker (backend) + Vercel (frontend)|

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
git clone https://github.com/your-username/bank-chatbot.git
cd bank-chatbot
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
python app\database\init_db.py
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

### 8. Chạy UI demo

```bash
cd frontend
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
│   │   │   └── database_logger.py
│   │   └── rag/
│   │       ├── cache/             # Redis + Semantic cache
│   │       ├── chains/            # LangChain chains (rewrite, decompose...)
│   │       ├── retrieval/         # Qdrant retriever, reranker, compressor
│   │       ├── routers/           # Intent & product routing
│   │       ├── utils/             # Logger, latency tracker, LLM client
│   │       └── pipeline.py        # Main RAG pipeline
│   ├── evaluate/                  # Evaluation scripts & datasets
│   ├── scripts/                   # Analysis & load testing scripts
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
└── docs/                          # Additional documentation
    ├── architecture.md
    ├── api.md
    └── evaluation.md
```

---

## API Reference

### `POST /chat`

Gửi tin nhắn và nhận stream response.

**Request body:**
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

Health check endpoint.

```json
{"status": "ok"}
```

---

## Tính năng nổi bật

### Pipeline tối ưu async

- **Bước 1**: Rewrite + Clarify check chạy song song
- **Bước 2**: Intent detection + Redis cache + Embedding chạy song song
- **Decompose task** bắt đầu ngay sau rewrite, chạy ngầm trong khi cache check
- Cache write là **fire-and-forget** — không block user response

### Dual-layer caching

- **Redis**: exact match trên rewritten query (~50ms)
- **Qdrant Semantic**: cosine similarity ≥ 0.92 (~1-2s)
- Cache hit rate trung bình: **~60-70%** sau warm-up

### Decompose pipeline

Query phức tạp tự động được tách thành sub-queries, mỗi sub-query có cache riêng và chạy song song.

---

## Evaluation

### Retrieval evaluation

```bash
cd backend
python evaluate/evaluate_retrieval.py
```

### End-to-end evaluation

```bash
python evaluate/end_to_end_evaluator.py
```

### Load testing

```bash
pip install locust
locust -f locustfile.py --host=http://localhost:8000 #or https://banking-chatbot-1-081l.onrender.com (server)

# Headless
locust -f locustfile.py --host=http://localhost:8000 \
  --users=20 --spawn-rate=2 --run-time=5m --headless --csv=results/normal
```

### Latency analysis

```bash
python scripts/analyze_latency.py --days 7
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

Cấu hình trong `render.yaml`:
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn api:app --host 0.0.0.0 --port $PORT`

---

## Kết quả đánh giá

| Metric | Value |
|---|---|
| Retrieval Hit Rate (k=15) | ~85% |
| Cache hit rate | ~65% |
| P50 latency (cache miss) | ~6s |
| P95 latency (cache miss) | ~10s |
| P50 latency (cache hit) | ~2s |

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
