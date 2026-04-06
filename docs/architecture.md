# Kiến trúc Pipeline

## Flow tổng quan

```
                     ┌──────────────┐
                     │  User Query  │
                     └──────┬───────┘
                            │
                   _preprocess_query()
                            │
          ┌─────────────────┴─────────────────┐
          │ BƯỚC 1 — Song song                │
          │  _invoke_rewrite()                │
          │  _invoke_clarify()                │
          └─────────────────┬─────────────────┘
                            │
          ┌─────────────────┴─────────────────┐
          │ BƯỚC 2 — Song song                │
          │  _detect_intent(rewritten)        │
          │  redis_cache.get(rewritten)       │
          │  retriever.embed(rewritten)       │
          │  [decompose_task nếu cần]         │
          └──────────────┬────────────────────┘
                         │
              ┌──────────┴──────────┐
              │  Route theo intent  │
              └──────────┬──────────┘
              │          │           │
           CHAT       OOS      KNOWLEDGE
              │          │           │
          stream      yield       continue
          chat         msg
                                    │
                        ┌───────────┴──────────┐
                        │  Clarify nếu cần     │
                        └───────────┬──────────┘
                                    │
                        ┌───────────┴──────────┐
                        │  Redis cache hit?    │
                        └───────────┬──────────┘
                               hit  │  miss
                          ┌─────────┴──────────┐
                          │  Semantic cache?    │
                          └─────────┬──────────┘
                               hit  │  miss
                                    │
                        ┌───────────┴──────────┐
                        │  _pipeline_from_     │
                        │  rewritten()         │
                        │  ├─ No decompose     │
                        │  │  └─ retrieve      │
                        │  │     → rerank      │
                        │  │     → compress    │
                        │  └─ Decompose        │
                        │     ├─ cache_check   │
                        │     ├─ retrieve      │
                        │     └─ merge context │
                        └───────────┬──────────┘
                                    │
                             stream_generator()
                                    │
                              yield tokens
```

## Optimization timeline

```
t=0                t=1.5s           t=2.8s           t=5s        t=8s
│                  │                │                 │           │
├── rewrite ───────┤                │                 │           │
├── clarify ───────┤                │                 │           │
                   ├── intent ──────┤                 │           │
                   ├── redis.get ───┤                 │           │
                   ├── embed ───────┤                 │           │
                   ├── decompose ───────────────────► │           │
                                    ├── semantic ─────┤           │
                                                      ├─ retrieve │
                                                      ├─ rerank   │
                                                      ├─ compress │
                                                                  ├ LLM
```

## Caching strategy

### L1 — Redis (exact match)

- Key: `rag:cache:md5(rewritten_query)`
- Value: `{"context": "..."}` (không cache response)
- TTL: 24h
- Hit rate: ~40-50%

### L2 — Qdrant Semantic

- Collection: `faq_cache`
- Vector: text-embedding-3-large (3072 dims)
- Threshold: cosine similarity ≥ 0.92
- Hit rate: ~15-20% sau L1 miss

### Cache write strategy

- **Fire-and-forget**: `asyncio.create_task()` — không block response
- **No re-embed**: dùng `add_with_vector()` với vector đã tính sẵn
- **Decompose**: cache theo từng sub_query, không cache rewritten

## Decompose pipeline

Khi query chứa "và", "hoặc", ",", "/" → tách thành sub-queries:

```
"Điều kiện vay A và hồ sơ vay B"
         │
   decompose_chain
         │
    ┌────┴────┐
    │         │
"Điều kiện  "Hồ sơ
  vay A"    vay B"
    │         │
  cache?    cache?
    │         │
  miss      miss
    │         │
retrieve   retrieve  ← song song với asyncio.gather
    │         │
rerank(5)  rerank(5)
    │         │
context1   context2
    └────┬────┘
         │
    merge context
         │
       LLM generate
```
