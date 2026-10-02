"""Seed Canonical Inventory and Policy Edges into Supabase PostgreSQL.

Reads:
- mydoc/dataset/canonical/projects.json -> projects table
- mydoc/dataset/canonical/units.json -> units table
- mydoc/dataset/canonical/mutual_exclusions.json -> policy_edges table
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import date
from pathlib import Path

# Fix Windows console encoding
sys.stdout.reconfigure(encoding="utf-8")

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import create_async_engine

from src.db.models import PolicyEdgeModel, ProjectModel, UnitModel

load_dotenv(ROOT_DIR / ".env")


async def seed_inventory():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is not set in environment or .env file.")

    engine = create_async_engine(db_url)

    canonical_dir = ROOT_DIR / "mydoc" / "dataset" / "canonical"
    projects_file = canonical_dir / "projects.json"
    units_file = canonical_dir / "units.json"
    exclusions_file = canonical_dir / "mutual_exclusions.json"

    print(f"Loading data from: {canonical_dir}")
    projects_data = json.loads(projects_file.read_text(encoding="utf-8"))
    units_data = json.loads(units_file.read_text(encoding="utf-8"))

    async with engine.begin() as conn:
        # 1. Seed Projects
        print(f"--- Seeding {len(projects_data)} projects ---")
        for p in projects_data:
            stmt = insert(ProjectModel).values(
                project_id=p["project_id"],
                tenant_id="DEFAULT",
                project_name=p["project_name"],
                legal_entity_name=p.get("developer", "VLand Future Group"),
            ).on_conflict_do_update(
                index_elements=["project_id"],
                set_={
                    "project_name": p["project_name"],
                    "legal_entity_name": p.get("developer", "VLand Future Group"),
                },
            )
            await conn.execute(stmt)
            print(f"  ✓ Seeded project: {p['project_id']} - {p['project_name']}")

        # 2. Seed Units
        print(f"--- Seeding {len(units_data)} units ---")
        for u in units_data:
            # Determine handover date from project or default 2027-12-31
            handover = date(2027, 12, 31)
            stmt = insert(UnitModel).values(
                unit_code=u["unit_code"],
                project_id=u["project_id"],
                unit_type=u.get("unit_type", "2BR"),
                floor_number=int(u.get("floor", 1)),
                listed_price_before_tax_vnd=int(u.get("listed_price_before_tax_vnd", 0)),
                handover_date=handover,
                status=u.get("availability_status", "AVAILABLE"),
            ).on_conflict_do_update(
                index_elements=["unit_code"],
                set_={
                    "project_id": u["project_id"],
                    "unit_type": u.get("unit_type", "2BR"),
                    "floor_number": int(u.get("floor", 1)),
                    "listed_price_before_tax_vnd": int(u.get("listed_price_before_tax_vnd", 0)),
                    "status": u.get("availability_status", "AVAILABLE"),
                },
            )
            await conn.execute(stmt)
        print(f"  ✓ Successfully seeded {len(units_data)} units!")

        # 3. Seed Policy Edges
        print(f"--- Seeding policy edges from {exclusions_file.name} ---")
        # Define edge mappings connecting representative atoms in DB
        edges_to_seed = [
            # CONF-01: Early Pay vs Bank Loan (Forward)
            {
                "edge_id": "EDGE-CONF-01",
                "source_atom_id": "POL-2026-VLF-EARLY__Điều_3_Điều_khoản_Loại_trừ_Tương_hỗ_(Hard_Exclusion)__Khoản_1__23ff16e4",
                "target_atom_id": "POL-2026-VLF-BANK__Điều_1_Tỷ_lệ_Cho_vay_&_Hỗ_trợ_Lãi_suất__Khoản_1__cf634a4c",
                "edge_type": "EXCLUDES",
                "source_authority": "CANONICAL_RULE",
                "validation_status": "APPROVED_FOR_USE",
                "edge_version": "v1",
                "description": "Chiết khấu thanh toán sớm 95% loại trừ tuyệt đối với Gói Vay hỗ trợ lãi suất ngân hàng (CONF-01).",
            },
            # CONF-01: Early Pay vs Bank Loan (Reverse for symmetric closure)
            {
                "edge_id": "EDGE-CONF-01-REV",
                "source_atom_id": "POL-2026-VLF-BANK__Điều_1_Tỷ_lệ_Cho_vay_&_Hỗ_trợ_Lãi_suất__Khoản_1__cf634a4c",
                "target_atom_id": "POL-2026-VLF-EARLY__Điều_3_Điều_khoản_Loại_trừ_Tương_hỗ_(Hard_Exclusion)__Khoản_1__23ff16e4",
                "edge_type": "EXCLUDES",
                "source_authority": "CANONICAL_RULE",
                "validation_status": "APPROVED_FOR_USE",
                "edge_version": "v1",
                "description": "Gói Vay hỗ trợ lãi suất loại trừ tuyệt đối với Chiết khấu thanh toán sớm 95% (CONF-01 Reverse).",
            },
            # CONF-02: Interior Gift vs Early Pay (Conditional)
            {
                "edge_id": "EDGE-CONF-02",
                "source_atom_id": "POL-2026-VLF-INTERIOR__Điều_2_Quy_định_Quy_đổi_Tiền_mặt__Khoản_1__4b4f1860",
                "target_atom_id": "POL-2026-VLF-EARLY__Điều_1_Điều_kiện_Hưởng_Chiết_khấu_Thanh_toán_Sớm__Khoản_1__1c3a08d4",
                "edge_type": "EXCLUDES",
                "source_authority": "CANONICAL_RULE",
                "validation_status": "APPROVED_FOR_USE",
                "edge_version": "v1",
                "description": "Căn hộ 3BR khi thanh toán sớm 95% chỉ được hưởng quà tặng nội thất quy đổi 50% tiền mặt (CONF-02).",
            },
            # CONF-03: VIP Exception Ceiling (Ambiguous Safe Abstain)
            {
                "edge_id": "EDGE-CONF-03",
                "source_atom_id": "POL-2026-VLF-VIP-EXP__Điều_2_Hướng_dẫn_Dừng_An_toàn_cho_Agent_(Safe_Abstention)__Khoản_1__dd6717e9",
                "target_atom_id": "POL-2026-VLF-GEN__Điều_1_Phạm_vi_Điều_chỉnh_&_Giá_Bán_Cơ_sở__Khoản_1__f41f7dcc",
                "edge_type": "EXCLUDES",
                "source_authority": "CANONICAL_RULE",
                "validation_status": "APPROVED_FOR_USE",
                "edge_version": "v1",
                "description": "Chính sách VIP vượt trần 10% bắt buộc có văn bản phê duyệt của TGĐ; Agent an toàn dừng suy đoán (CONF-03).",
            },
        ]

        for e in edges_to_seed:
            stmt = insert(PolicyEdgeModel).values(**e).on_conflict_do_update(
                index_elements=["edge_id"],
                set_={
                    "source_atom_id": e["source_atom_id"],
                    "target_atom_id": e["target_atom_id"],
                    "edge_type": e["edge_type"],
                    "validation_status": e["validation_status"],
                    "description": e["description"],
                },
            )
            await conn.execute(stmt)
            print(f"  ✓ Seeded edge: {e['edge_id']} ({e['edge_type']}) -> {e['description'][:50]}...")

    # Verification query
    async with engine.connect() as conn:
        p_count = (await conn.execute(text("SELECT count(*) FROM projects"))).scalar()
        u_count = (await conn.execute(text("SELECT count(*) FROM units"))).scalar()
        e_count = (await conn.execute(text("SELECT count(*) FROM policy_edges"))).scalar()
        print("\n=== VERIFICATION SUMMARY ===")
        print(f"projects rows: {p_count}")
        print(f"units rows   : {u_count}")
        print(f"policy_edges : {e_count}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_inventory())
