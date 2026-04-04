"""
scripts/compare_results.py — So sánh kết quả các scenario load test

Chạy:
    python scripts/compare_results.py results/20240403_1200
"""

import sys
import csv
from pathlib import Path


SCENARIOS = ["baseline", "normal", "peak", "stress"]
USERS     = {"baseline": 5, "normal": 20, "peak": 50, "stress": 100}
THRESHOLDS = {
    "p95_ok":    12000,
    "p95_warn":  18000,
    "fail_ok":   1.0,
    "fail_warn": 5.0,
}


def load_stats(results_dir: Path, scenario: str) -> dict | None:
    path = results_dir / f"{scenario}_stats.csv"
    if not path.exists():
        return None

    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("Name") == "/chat" and row.get("Type") == "POST":
                total = int(row.get("Request Count", 0) or 0)
                fails = int(row.get("Failure Count", 0) or 0)
                return {
                    "users":    USERS[scenario],
                    "total":    total,
                    "fails":    fails,
                    "fail_pct": fails / max(total, 1) * 100,
                    "p50":      float(row.get("50%", 0) or 0),
                    "p90":      float(row.get("90%", 0) or 0),
                    "p95":      float(row.get("95%", 0) or 0),
                    "p99":      float(row.get("99%", 0) or 0),
                    "rps":      float(row.get("Requests/s", 0) or 0),
                    "avg":      float(row.get("Average (ms)", 0) or 0),
                }
    return None


def status(p95: float, fail_pct: float) -> str:
    if fail_pct > THRESHOLDS["fail_warn"] or p95 > THRESHOLDS["p95_warn"]:
        return "🔴 FAIL"
    if fail_pct > THRESHOLDS["fail_ok"] or p95 > THRESHOLDS["p95_ok"]:
        return "🟡 WARN"
    return "✅ OK  "


def compare(results_dir: Path):
    print(f"\nResults: {results_dir}")
    print("\n" + "=" * 80)
    print(f"  {'Scenario':<12} {'Users':>5} {'P50':>8} {'P90':>8} {'P95':>8} {'P99':>8} {'RPS':>6} {'Fail%':>6}  Status")
    print("-" * 80)

    prev_p95 = None
    for scenario in SCENARIOS:
        r = load_stats(results_dir, scenario)
        if not r:
            print(f"  {scenario:<12}  — no data")
            continue

        st = status(r["p95"], r["fail_pct"])
        degradation = ""
        if prev_p95 and r["p95"] > prev_p95 * 1.5:
            degradation = f"  ↑{r['p95']/prev_p95:.1f}x"

        print(
            f"  {scenario:<12} {r['users']:>5} "
            f"{r['p50']:>7.0f}ms {r['p90']:>7.0f}ms {r['p95']:>7.0f}ms {r['p99']:>7.0f}ms "
            f"{r['rps']:>5.1f} {r['fail_pct']:>5.1f}%  {st}{degradation}"
        )
        prev_p95 = r["p95"]

    print("=" * 80)

    # Find breaking point
    for scenario in SCENARIOS:
        r = load_stats(results_dir, scenario)
        if r and (r["fail_pct"] > THRESHOLDS["fail_warn"] or r["p95"] > THRESHOLDS["p95_warn"]):
            print(f"\n  ⚠ System starts degrading at {r['users']} concurrent users")
            print(f"    P95={r['p95']:.0f}ms, fail_rate={r['fail_pct']:.1f}%")
            break
    else:
        last = load_stats(results_dir, SCENARIOS[-1])
        if last:
            print(f"\n  ✅ System stable up to {last['users']} concurrent users")

    print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/compare_results.py <results_dir>")
        sys.exit(1)
    compare(Path(sys.argv[1]))