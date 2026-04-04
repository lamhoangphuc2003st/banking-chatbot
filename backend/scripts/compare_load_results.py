# scripts/compare_load_results.py
import csv
from pathlib import Path


def load_csv(path: str) -> dict:
    results = {}
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["Name"] == "/chat":
                results = {
                    "p50": float(row.get("50%", 0)),
                    "p95": float(row.get("95%", 0)),
                    "p99": float(row.get("99%", 0)),
                    "rps": float(row.get("Requests/s", 0)),
                    "fail_rate": float(row.get("Failure Count", 0)) /
                                 max(float(row.get("Request Count", 1)), 1) * 100,
                }
    return results


def compare():
    scenarios = [
        ("Baseline (5 users)",  "backend/results/baseline_stats.csv"),
        ("Normal (20 users)",   "backend/results/normal_stats.csv"),
        ("Peak (50 users)",     "backend/results/peak_stats.csv"),
        ("Stress (100 users)",  "backend/results/stress_stats.csv"),
    ]

    print(f"\n{'Scenario':<22} {'P50':>8} {'P95':>8} {'P99':>8} {'RPS':>8} {'Fail%':>8}")
    print("-" * 62)

    for name, path in scenarios:
        if not Path(path).exists():
            continue
        r = load_csv(path)
        fail_marker = " ⚠️" if r["fail_rate"] > 1 else ""
        print(
            f"{name:<22} {r['p50']:>7.0f}ms {r['p95']:>7.0f}ms "
            f"{r['p99']:>7.0f}ms {r['rps']:>7.1f} {r['fail_rate']:>7.1f}%{fail_marker}"
        )


if __name__ == "__main__":
    compare()