"""
evaluate_retrieval.py — Chạy toàn bộ test cases và đo Hit Rate + MRR.

Usage:
    python evaluate_retrieval.py

Output:
    - In kết quả ra terminal
    - Lưu retrieval_results.json (chi tiết từng case)
    - Lưu retrieval_report.csv (để mở bằng Excel)
"""

import asyncio
import json
import time
import csv
from collections import defaultdict
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# Adjust import path nếu cần
import sys
sys.path.insert(0, ".")
from app.rag.retrieval.qdrant_retriever import QdrantRetriever


async def evaluate(test_cases: list[dict], k: int = 15) -> dict:
    retriever = QdrantRetriever()
    results = []

    total = len(test_cases)
    hit = 0
    mrr_sum = 0.0
    t0 = time.time()

    for i, case in enumerate(test_cases, 1):
        doc_id = case["doc_id"]
        query = case["query"]

        try:
            docs = await retriever.search(query, k=k)
            retrieved_ids = [d["doc_id"] for d in docs]

            found = doc_id in retrieved_ids
            rank = retrieved_ids.index(doc_id) + 1 if found else None

            if found:
                hit += 1
                mrr_sum += 1 / rank

            results.append({
                **case,
                "hit": found,
                "rank": rank,
                "retrieved_ids": retrieved_ids[:5],  # lưu top-5 để debug
            })

        except Exception as e:
            results.append({
                **case,
                "hit": False,
                "rank": None,
                "error": str(e),
                "retrieved_ids": [],
            })

        if i % 20 == 0:
            elapsed = time.time() - t0
            print(f"  [{i}/{total}] Hit so far: {hit}/{i} ({hit/i*100:.1f}%) | {elapsed:.1f}s")

    elapsed = time.time() - t0
    hit_rate = hit / total
    mrr = mrr_sum / total

    # Breakdown theo section
    by_section = defaultdict(lambda: {"total": 0, "hit": 0})
    for r in results:
        s = r.get("section", "unknown")
        by_section[s]["total"] += 1
        if r["hit"]:
            by_section[s]["hit"] += 1

    # Breakdown theo type
    by_type = defaultdict(lambda: {"total": 0, "hit": 0})
    for r in results:
        t = r.get("type", "unknown")
        by_type[t]["total"] += 1
        if r["hit"]:
            by_type[t]["hit"] += 1

    report = {
        "k": k,
        "total": total,
        "hit": hit,
        "hit_rate": round(hit_rate, 4),
        "mrr": round(mrr, 4),
        "elapsed_s": round(elapsed, 1),
        "by_section": {
            s: {
                "hit_rate": round(v["hit"] / v["total"], 3),
                "hit": v["hit"],
                "total": v["total"],
            }
            for s, v in sorted(by_section.items())
        },
        "by_type": {
            t: {
                "hit_rate": round(v["hit"] / v["total"], 3),
                "hit": v["hit"],
                "total": v["total"],
            }
            for t, v in sorted(by_type.items())
        },
        "misses": [r for r in results if not r["hit"]],
    }

    return report, results


def print_report(report: dict):
    print("\n" + "=" * 55)
    print(f"  RETRIEVAL EVALUATION  (k={report['k']})")
    print("=" * 55)
    print(f"  Total   : {report['total']}")
    print(f"  Hit Rate: {report['hit_rate']*100:.1f}%  ({report['hit']}/{report['total']})")
    print(f"  MRR     : {report['mrr']:.4f}")
    print(f"  Time    : {report['elapsed_s']}s")

    print("\n  By Type:")
    for t, v in report["by_type"].items():
        bar = "█" * int(v["hit_rate"] * 20)
        print(f"    {t:8s}: {v['hit_rate']*100:5.1f}%  {bar}  ({v['hit']}/{v['total']})")

    print("\n  By Section:")
    for s, v in report["by_section"].items():
        bar = "█" * int(v["hit_rate"] * 20)
        print(f"    {s:35s}: {v['hit_rate']*100:5.1f}%  ({v['hit']}/{v['total']})")

    print(f"\n  Misses: {len(report['misses'])}")
    print("  Top missed queries:")
    for m in report["misses"][:10]:
        print(f"    [{m['section']:15s}] {m['product']:30s} | {m['query'][:60]}")
    print("=" * 55)


async def main():
    here = Path(__file__).resolve().parent
    test_file = here / "retrieval_test_cases.json"

    with open(test_file, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    print(f"Running {len(test_cases)} test cases with k=15...")
    report, results = await evaluate(test_cases, k=15)

    print_report(report)

    # Save full results
    with open(here / "retrieval_results.json", "w", encoding="utf-8") as f:
        save_report = {k: v for k, v in report.items() if k != "misses"}
        save_report["misses_count"] = len(report["misses"])
        json.dump({"summary": save_report, "details": results}, f, ensure_ascii=False, indent=2)

    # Save CSV for Excel
    with open(here / "retrieval_report.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["doc_id", "query", "product", "section", "type", "hit", "rank"])
        writer.writeheader()
        for r in results:
            writer.writerow({
                "doc_id": r["doc_id"],
                "query": r["query"],
                "product": r.get("product", ""),
                "section": r.get("section", ""),
                "type": r.get("type", ""),
                "hit": r["hit"],
                "rank": r.get("rank", ""),
            })

    print("\nSaved: retrieval_results.json, retrieval_report.csv")


if __name__ == "__main__":
    asyncio.run(main())