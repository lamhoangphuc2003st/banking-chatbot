# Makefile — Vietcombank RAG Chatbot
# Chạy: make <target>

.PHONY: help install dev lint test evaluate load-test analyze clean

# ================================
# Help
# ================================
help:
	@echo ""
	@echo "  Vietcombank RAG Chatbot — Available commands:"
	@echo ""
	@echo "  Setup:"
	@echo "    make install        Cài đặt dependencies"
	@echo "    make db-init        Khởi tạo database tables"
	@echo "    make ingest         Ingest data vào Qdrant"
	@echo ""
	@echo "  Development:"
	@echo "    make dev            Chạy server development (reload)"
	@echo "    make lint           Kiểm tra code style"
	@echo ""
	@echo "  Evaluation:"
	@echo "    make eval-retrieval Đánh giá retrieval pipeline"
	@echo "    make eval-e2e       Đánh giá end-to-end"
	@echo "    make analyze        Phân tích latency từ DB"
	@echo ""
	@echo "  Load Testing:"
	@echo "    make load-baseline  5 users, 2 phút"
	@echo "    make load-normal    20 users, 5 phút"
	@echo "    make load-peak      50 users, 5 phút"
	@echo "    make load-stress    100 users, 5 phút"
	@echo "    make load-all       Chạy tất cả scenarios"
	@echo "    make load-compare   So sánh kết quả"
	@echo ""
	@echo "  Docker:"
	@echo "    make docker-build   Build Docker image"
	@echo "    make docker-run     Chạy Docker container"
	@echo ""

# ================================
# Setup
# ================================
install:
	pip install -r backend/requirements.txt

db-init:
	cd backend && psql $$DATABASE_URL -f app/database/migrations/001_init.sql
	cd backend && psql $$DATABASE_URL -f app/database/migrations/002_add_latency_columns.sql

ingest:
	cd backend && python vectorstore/ingest_qdrant.py

# ================================
# Development
# ================================
dev:
	cd backend && uvicorn api:app --host 0.0.0.0 --port 8000 --reload

lint:
	cd backend && python -m flake8 app/ --max-line-length=120 --exclude=__pycache__

# ================================
# Evaluation
# ================================
eval-retrieval:
	cd backend && python evaluate/evaluate_retrieval.py

eval-e2e:
	cd backend && python evaluate/end_to_end_evaluator.py

analyze:
	cd backend && python scripts/analyze_latency.py --days 7

bottlenecks:
	cd backend && python scripts/check_bottlenecks.py

# ================================
# Load Testing
# ================================
HOST ?= http://localhost:8000

load-baseline:
	@mkdir -p backend/results
	cd backend && locust -f locustfile.py --host=$(HOST) \
	  --users=5 --spawn-rate=1 --run-time=2m --headless \
	  --csv=results/baseline --html=results/baseline.html

load-normal:
	@mkdir -p backend/results
	cd backend && locust -f locustfile.py --host=$(HOST) \
	  --users=20 --spawn-rate=2 --run-time=5m --headless \
	  --csv=results/normal --html=results/normal.html

load-peak:
	@mkdir -p backend/results
	cd backend && locust -f locustfile.py --host=$(HOST) \
	  --users=50 --spawn-rate=5 --run-time=5m --headless \
	  --csv=results/peak --html=results/peak.html

load-stress:
	@mkdir -p backend/results
	cd backend && locust -f locustfile.py --host=$(HOST) \
	  --users=100 --spawn-rate=10 --run-time=5m --headless \
	  --csv=results/stress --html=results/stress.html

load-all: load-baseline load-normal load-peak load-stress load-compare

load-compare:
	cd backend && python scripts/compare_load_results.py

load-ui:
	cd backend && locust -f locustfile.py --host=$(HOST)

# ================================
# Docker
# ================================
docker-build:
	docker build -t bank-chatbot ./backend

docker-run:
	docker run -p 8000:8000 --env-file backend/.env bank-chatbot

# ================================
# Clean
# ================================
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf backend/results/*.csv backend/results/*.html 2>/dev/null || true
