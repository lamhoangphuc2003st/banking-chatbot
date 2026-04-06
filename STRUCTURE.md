# Cấu trúc repo mục tiêu

Sau khi tổ chức lại, repo nên có cấu trúc như sau:

```
bank-chatbot/                          ← root
├── README.md                          ← ✅ Cần tạo
├── Makefile                           ← ✅ Cần tạo
├── .gitignore                         ← ✅ Cần cập nhật
├── LICENSE                            ← Cần tạo
│
├── backend/
│   ├── app/
│   │   ├── __init__.py                ← Cần tạo (package)
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── migrations/
│   │   │   │   ├── 001_init.sql
│   │   │   │   └── 002_add_latency_columns.sql
│   │   │   ├── connection.py
│   │   │   ├── database_logger.py
│   │   │   └── init_db.py
│   │   └── rag/
│   │       ├── __init__.py
│   │       ├── pipeline.py            ← Chuyển từ utils/
│   │       ├── cache/
│   │       │   ├── __init__.py
│   │       │   ├── redis_cache.py
│   │       │   └── semantic_cache.py
│   │       ├── chains/
│   │       │   ├── __init__.py
│   │       │   ├── clarify_chain.py
│   │       │   ├── decompose_chain.py
│   │       │   ├── generator_chain.py
│   │       │   └── rewrite_chain.py
│   │       ├── retrieval/
│   │       │   ├── __init__.py
│   │       │   ├── compression.py
│   │       │   ├── qdrant_retriever.py
│   │       │   └── reranker.py
│   │       ├── routers/
│   │       │   ├── __init__.py
│   │       │   └── intent_router.py
│   │       └── utils/
│   │           ├── __init__.py
│   │           ├── context_builder.py
│   │           ├── latency_tracker.py
│   │           ├── llm_client.py
│   │           └── logger.py
│   │
│   ├── evaluate/
│   │   ├── golden_dataset.json        ← Git tracked (manually curated)
│   │   ├── retrieval_test_cases.json  ← Git tracked
│   │   ├── build_golden_from_retrieval.py
│   │   ├── end_to_end_evaluator.py
│   │   ├── evaluate_retrieval.py
│   │   └── generate_test_cases.py
│   │
│   ├── scripts/
│   │   ├── analyze_latency.py
│   │   ├── check_bottlenecks.py
│   │   ├── compare_load_results.py
│   │   ├── compare_results.py
│   │   └── run_load_tests.sh
│   │
│   ├── vectorstore/
│   │   └── ingest_qdrant.py
│   │
│   ├── data/
│   │   ├── vietcombank_chunks.json    ← Git tracked
│   │   └── vietcombank_corpus.json    ← Git tracked
│   │   # faiss_index.bin             ← .gitignore (legacy)
│   │   # *_older.json                ← .gitignore (outdated)
│   │
│   ├── results/                       ← .gitignore (auto-generated CSV)
│   │   └── .gitkeep
│   │
│   ├── api.py
│   ├── locustfile.py
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── .env.example                   ← ✅ Cần tạo
│   └── runtime.txt
│
├── crawler/
│   ├── raw/                           ← Raw scraped data
│   ├── normalizer/                    ← Đổi từ "nomalizer" (typo)
│   │   ├── normalized/
│   │   ├── normalize_credit.py
│   │   ├── normalize_credit_faq.py
│   │   ├── normalize_loan.py
│   │   └── normalize_loan_faq.py
│   ├── chunk/
│   │   └── chunker.py
│   ├── credit_crawler.py
│   ├── credit_faq_crawler.py
│   ├── loan_crawler.py
│   └── loan_faq_crawler.py
│
├── frontend/
│
└── docs/                              ← ✅ Cần tạo
    ├── architecture.md
    └── evaluation.md
```

## Các thay đổi cần thực hiện

### Bắt buộc
1. **Thêm `__init__.py`** vào mỗi package folder
2. **Di chuyển `pipeline.py`** từ `app/rag/utils/` → `app/rag/pipeline.py`
3. **Đổi tên** `nomalizer/` → `normalizer/`
4. **Xóa** `test.py`, `test1.py` ở root backend (hoặc chuyển vào `tests/`)
5. **Tạo** `.env.example`

### Nên làm
6. **Tạo** `README.md` ở root
7. **Tạo** `Makefile`
8. **Cập nhật** `.gitignore` để exclude results/, *.pyc, .env
9. **Tạo** `docs/` folder

### Tuỳ chọn
10. **Tạo** `LICENSE` (MIT)
11. **Tạo** `CONTRIBUTING.md`
12. **Thêm** `tests/` folder với unit tests
