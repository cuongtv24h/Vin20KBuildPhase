.PHONY: run test lint format typecheck check clean

run:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

typecheck:
	mypy src/

check: lint format test

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +

seed-data:
	python scripts/seed_data.py --dry-run

sidecar:
	python -m src.pricing_sidecar

prototype:
	python scripts/serve_prototype.py
