#!/bin/bash
# scripts/run_load_tests.sh
# Chạy tuần tự 4 scenario và lưu kết quả

HOST="${1:-http://localhost:8000}"
RESULTS_DIR="results/$(date +%Y%m%d_%H%M)"
mkdir -p "$RESULTS_DIR"

echo "Load testing $HOST → $RESULTS_DIR"
echo ""

run_scenario() {
    local name=$1
    local users=$2
    local spawn=$3
    local duration=$4

    echo "▶ $name ($users users, ${duration}s)..."
    locust -f locustfile.py \
        --host="$HOST" \
        --users="$users" \
        --spawn-rate="$spawn" \
        --run-time="${duration}s" \
        --headless \
        --csv="$RESULTS_DIR/$name" \
        --html="$RESULTS_DIR/${name}.html" \
        2>&1 | tail -5
    echo "  Done → $RESULTS_DIR/$name"
    echo ""
    sleep 10   # cooldown
}

run_scenario "baseline"  5   1  120
run_scenario "normal"    20  2  300
run_scenario "peak"      50  5  300
run_scenario "stress"    100 10 300

echo "All done. Comparing results..."
python scripts/compare_results.py "$RESULTS_DIR"