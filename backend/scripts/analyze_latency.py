"""
scripts/analyze_latency.py
Phân tích latency từ bảng rag_logs.

Chạy:
    cd backend
    python scripts/analyze_latency.py              # 7 ngày gần nhất
    python scripts/analyze_latency.py --days 30    # 30 ngày
    python scripts/analyze_latency.py --hours 24   # 24 giờ gần nhất
"""

import sys
import json
import argparse
from datetime import datetime, timedelta
from collections import defaultdict
from dotenv import load_dotenv

sys.path.insert(0, ".")
from app.database.connection import get_connection

load_dotenv()

# -------------------------------------------------------
# Data fetching
# -------------------------------------------------------

def fetch_logs(since: datetime) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            session_id, query, rewritten, intent,
            cache_type, clarification,
            latency_ms, retrieval_latency_ms,
            decomposed, latency_breakdown, error,
            created_at
        FROM rag_logs
        WHERE created_at >= %s
        ORDER BY created_at DESC
    """, (since,))

    cols = [desc[0] for desc in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()

    # Parse JSON fields
    for row in rows:
        for field in ("decomposed", "latency_breakdown"):
            val = row.get(field)
            if isinstance(val, str):
                try:
                    row[field] = json.loads(val)
                except Exception:
                    row[field] = None

    return rows


# -------------------------------------------------------
# Stats helpers
# -------------------------------------------------------

def pct(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    idx = max(0, min(int(len(s) * p / 100), len(s) - 1))
    return s[idx]


def stats_block(latencies: list[float], label: str, count: int):
    if not latencies:
        return
    print(f"\n  [{label}]  ({count} requests)")
    print(f"    P50  : {pct(latencies, 50):>7.0f} ms")
    print(f"    P75  : {pct(latencies, 75):>7.0f} ms")
    print(f"    P90  : {pct(latencies, 90):>7.0f} ms")
    print(f"    P95  : {pct(latencies, 95):>7.0f} ms")
    print(f"    P99  : {pct(latencies, 99):>7.0f} ms")
    print(f"    Max  : {max(latencies):>7.0f} ms")
    print(f"    Mean : {sum(latencies)/len(latencies):>7.0f} ms")


def bar(value: float, max_val: float, width: int = 20) -> str:
    if max_val == 0:
        return ""
    filled = int(value / max_val * width)
    return "█" * filled + "░" * (width - filled)


# -------------------------------------------------------
# Main report
# -------------------------------------------------------

def analyze(logs: list[dict]):
    if not logs:
        print("  Không có dữ liệu.")
        return

    total = len(logs)
    errors = [l for l in logs if l.get("error")]

    # Phân loại theo path
    redis_logs     = [l for l in logs if l.get("cache_type") == "redis"]
    semantic_logs  = [l for l in logs if l.get("cache_type") == "semantic"]
    clarify_logs   = [l for l in logs if l.get("clarification")]
    decompose_logs = [l for l in logs if l.get("decomposed") and len(l["decomposed"]) > 1]
    normal_logs    = [
        l for l in logs
        if not l.get("cache_type")
        and not l.get("clarification")
        and not (l.get("decomposed") and len(l["decomposed"]) > 1)
    ]

    def latencies(log_list):
        return [l["latency_ms"] for l in log_list if l.get("latency_ms")]

    print("\n" + "=" * 65)
    print(f"  LATENCY REPORT  ({total} requests)")
    print("=" * 65)

    # --- Overall ---
    stats_block(latencies(logs), "Overall", total)

    # --- By path ---
    stats_block(latencies(redis_logs),    f"Redis cache hit",    len(redis_logs))
    stats_block(latencies(semantic_logs), f"Semantic cache hit", len(semantic_logs))
    stats_block(latencies(normal_logs),   f"Cache miss (no decompose)", len(normal_logs))
    stats_block(latencies(decompose_logs),f"Decompose",          len(decompose_logs))
    stats_block(latencies(clarify_logs),  f"Clarification",      len(clarify_logs))

    # --- Retrieval vs Generation breakdown ---
    breakdown_logs = [
        l for l in logs
        if l.get("latency_breakdown") and l.get("latency_ms")
    ]
    if breakdown_logs:
        print(f"\n  Latency breakdown (avg, {len(breakdown_logs)} requests với tracker):")
        step_totals = defaultdict(list)
        for l in breakdown_logs:
            deltas = l["latency_breakdown"].get("deltas_ms", {})
            for k, v in deltas.items():
                step_totals[k].append(v)
        for step, values in sorted(step_totals.items()):
            avg = sum(values) / len(values)
            print(f"    {step:<30s}: {avg:>6.0f} ms avg")

    # --- Cache stats ---
    print(f"\n  Cache Stats:")
    total_cache = len(redis_logs) + len(semantic_logs)
    print(f"    Redis hit rate   : {len(redis_logs)/total*100:>5.1f}%  ({len(redis_logs)}/{total})")
    print(f"    Semantic hit rate: {len(semantic_logs)/total*100:>5.1f}%  ({len(semantic_logs)}/{total})")
    print(f"    Total cache rate : {total_cache/total*100:>5.1f}%  ({total_cache}/{total})")

    # --- Intent distribution ---
    intents = defaultdict(int)
    for l in logs:
        intents[l.get("intent") or "unknown"] += 1
    print(f"\n  Intent Distribution:")
    for intent, count in sorted(intents.items(), key=lambda x: -x[1]):
        b = bar(count, total)
        print(f"    {intent:<15s}: {count:>4}  {b}  {count/total*100:.1f}%")

    # --- Errors ---
    print(f"\n  Errors: {len(errors)}/{total} ({len(errors)/total*100:.1f}%)")
    for e in errors[:5]:
        print(f"    [{e.get('created_at', '')!s:.19s}] {e.get('error', '')[:80]}")

    # --- Hourly P95 ---
    hourly = defaultdict(list)
    for l in logs:
        created = l.get("created_at")
        if created and l.get("latency_ms"):
            hour = created.hour if hasattr(created, "hour") else 0
            hourly[hour].append(l["latency_ms"])

    if hourly:
        print(f"\n  Latency P95 by Hour:")
        max_p95 = max(pct(v, 95) for v in hourly.values())
        for hour in sorted(hourly.keys()):
            p95 = pct(hourly[hour], 95)
            b = bar(p95, max_p95)
            print(f"    {hour:02d}:00  {p95:>7.0f} ms  {b}  ({len(hourly[hour])} req)")

    # --- Slow requests ---
    slow = [
        l for l in logs
        if l.get("latency_ms") is not None
        and l["latency_ms"] > 15000
    ]
    if slow:
        print(f"\n  Slow Requests (>15s): {len(slow)}")
        for l in slow[:10]:
            sub = len(l.get("decomposed") or [])
            print(
                f"    {l['latency_ms']:>6}ms | cache={l.get('cache_type') or 'miss':8s} "
                f"| subs={sub} | {(l.get('rewritten') or l.get('query') or '')[:55]}"
            )

    print("\n" + "=" * 65)


# -------------------------------------------------------
# Entrypoint
# -------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Analyze RAG pipeline latency")
    parser.add_argument("--days", type=int, default=7, help="Số ngày lookback (default: 7)")
    parser.add_argument("--hours", type=int, default=None, help="Số giờ lookback (override --days)")
    args = parser.parse_args()

    if args.hours:
        since = datetime.now() - timedelta(hours=args.hours)
        label = f"last {args.hours} hours"
    else:
        since = datetime.now() - timedelta(days=args.days)
        label = f"last {args.days} days"

    print(f"Fetching logs since {since.strftime('%Y-%m-%d %H:%M')} ({label})...")
    logs = fetch_logs(since)
    print(f"Loaded {len(logs)} records.")
    analyze(logs)


if __name__ == "__main__":
    main()

# python scripts/analyze_latency.py --days 7