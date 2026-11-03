.PHONY: help up down test demo api e2e

help:
	@echo "DriftGuard Automation Commands:"
	@echo "  make up      - Start Docker infrastructure (Postgres + mitmproxy)"
	@echo "  make down    - Stop Docker containers"
	@echo "  make demo    - Run Demo Shop (port 3001)"
	@echo "  make api     - Run DriftGuard Engine API (port 8000)"
	@echo "  make e2e     - Run automated F1 end-to-end chaos test"
	@echo "  make test    - Run Python unit test suite"

up:
	docker compose up -d

down:
	docker compose down

demo:
	cd targets/demo-shop && npx tsx src/server.ts

api:
	uvicorn engine.api.main:app --port 8000 --reload

test:
	pytest evals/

e2e:
	python engine/orchestrator/runner.py

