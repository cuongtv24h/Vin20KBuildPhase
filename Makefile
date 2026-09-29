.PHONY: run test lint format typecheck check clean eval

run:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v

eval:
	python scripts/run_eval.py

lint:
	ruff check src/ tests/ eval/ scripts/

format:
	ruff format src/ tests/ eval/ scripts/

typecheck:
	mypy src/

check: lint format test

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
