-- migrations/001_add_latency_columns.sql
-- Chạy 1 lần để thêm các cột mới vào bảng rag_logs

ALTER TABLE rag_logs
    ADD COLUMN IF NOT EXISTS retrieval_latency_ms  INTEGER,
    ADD COLUMN IF NOT EXISTS cache_type            VARCHAR(20),   -- 'redis' | 'semantic' | NULL
    ADD COLUMN IF NOT EXISTS clarification         BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS mentioned_products    JSONB,
    ADD COLUMN IF NOT EXISTS decomposed            JSONB,
    ADD COLUMN IF NOT EXISTS latency_breakdown     JSONB,         -- từ LatencyTracker
    ADD COLUMN IF NOT EXISTS error                 TEXT,
    ADD COLUMN IF NOT EXISTS created_at            TIMESTAMPTZ DEFAULT NOW();

-- Index để query nhanh theo thời gian và cache_type
CREATE INDEX IF NOT EXISTS idx_rag_logs_created_at  ON rag_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rag_logs_cache_type  ON rag_logs (cache_type);
CREATE INDEX IF NOT EXISTS idx_rag_logs_intent      ON rag_logs (intent);
CREATE INDEX IF NOT EXISTS idx_rag_logs_latency     ON rag_logs (latency_ms);

-- View tiện dùng cho analyze script
CREATE OR REPLACE VIEW rag_logs_summary AS
SELECT
    session_id,
    query,
    rewritten,
    intent,
    cache_type,
    clarification,
    latency_ms,
    retrieval_latency_ms,
    latency_ms - COALESCE(retrieval_latency_ms, latency_ms) AS generation_latency_ms,
    jsonb_array_length(COALESCE(decomposed, '[]')) AS num_subqueries,
    error IS NOT NULL AS has_error,
    created_at
FROM rag_logs;