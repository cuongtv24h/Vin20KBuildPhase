#!/usr/bin/env python3
"""RAG Evaluation Runner Script.

Usage:
    python scripts/run_eval.py
    # or:
    make eval
"""
import logging
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.rag.runner import RAGEvaluator  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("eval_runner")


def resolve_path(env_var: str, rel_path: str, fallback: str) -> str:
    if os.getenv(env_var):
        return os.environ[env_var]
    candidate = (PROJECT_ROOT / rel_path).resolve()
    return str(candidate) if candidate.exists() else fallback


def main():
    dataset_path = resolve_path(
        "EVAL_DATASET_PATH",
        "../report/Dataset/fixtures/golden_scenarios.json",
        "/Users/mac/AITC/PROJECT/report/Dataset/fixtures/golden_scenarios.json",
    )
    policies_dir = resolve_path(
        "EVAL_POLICIES_DIR",
        "../report/Dataset/policies_md",
        "/Users/mac/AITC/PROJECT/report/Dataset/policies_md",
    )
    canonical_dir = resolve_path(
        "EVAL_CANONICAL_DIR",
        "../report/Dataset/canonical",
        "/Users/mac/AITC/PROJECT/report/Dataset/canonical",
    )
    output_dir = os.getenv("EVAL_OUTPUT_DIR", "eval/results")

    logger.info("Initializing RAG Evaluator from scripts/run_eval.py...")
    evaluator = RAGEvaluator(
        dataset_path=dataset_path,
        policies_dir=policies_dir,
        canonical_dir=canonical_dir,
    )

    evaluator.setup()
    evaluator.run()
    evaluator.generate_report(output_dir)


if __name__ == "__main__":
    main()
