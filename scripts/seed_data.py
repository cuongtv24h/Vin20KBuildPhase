#!/usr/bin/env python3
"""Nạp dữ liệu mẫu (`mydoc/dataset/`) vào DB / vector store.

Dữ liệu ground truth của dự án:
- canonical/*.json        — projects, units (40 căn), policies (10), mutual_exclusions
- policies_md/POL-*.md    — văn bản chính sách sạch cho chunking + vector search
- fixtures/*.json         — personas, golden scenarios (Δ=0), compliance messages

Chạy dry-run (không cần DB):
    python scripts/seed_data.py --dry-run
"""

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "mydoc" / "dataset"

CANONICAL_FILES = ("projects.json", "units.json", "policies.json", "mutual_exclusions.json")


def load_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed dữ liệu mẫu PricePolicy AI Agent")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ đọc và in thống kê")
    args = parser.parse_args()

    for name in CANONICAL_FILES:
        data = load_json(DATASET_DIR / "canonical" / name)
        print(f"[canonical] {name}: {len(data)} bản ghi")

    policies_md = sorted((DATASET_DIR / "policies_md").glob("POL-*.md"))
    print(f"[policies_md] {len(policies_md)} văn bản chính sách")

    golden = load_json(DATASET_DIR / "fixtures" / "golden_scenarios.json")
    print(f"[fixtures] golden_scenarios: {len(golden)} cases")
    compliance = load_json(DATASET_DIR / "fixtures" / "compliance_messages.json")
    print(f"[fixtures] compliance_messages: {len(compliance)} mẫu")

    if args.dry_run:
        print("\n--dry-run: không ghi DB. Khi implement C-02/C-03, nạp tiếp vào")
        print("Supabase + pgvector qua src.services.rag.ingestion.PolicyIngestionPipeline.")
        return

    raise NotImplementedError("Seed DB chưa implement — cần Supabase/pgvector (C-02, C-03)")


if __name__ == "__main__":
    main()
