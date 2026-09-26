"""Golden benchmark kế toán (Dev 2) — bất biến Δ = 0 VNĐ trên dữ liệu thật.

Load `mydoc/dataset/fixtures/golden_scenarios.json` (nguồn chuẩn tắc) và xác
minh quan hệ kế toán giữa các trường. Khi C-06 implement, phần ASSERT_ENTITY
sẽ đối soát output của `DeterministicPricingEngine` với expected values.

Mục tiêu theo ImplementPlan: 15 golden cases Exact Match 100% — dataset đang
có 2 case (BENCH-01, BENCH-02), bổ sung dần trong Spike 1.
"""

import json
from decimal import Decimal
from pathlib import Path

DATASET = Path(__file__).resolve().parents[2] / "mydoc" / "dataset" / "fixtures" / "golden_scenarios.json"

VAT_RATE = Decimal("0.10")  # POL-01
MAINTENANCE_RATE = Decimal("0.02")  # POL-01 — KPBT 2%

REQUIRED_FIELDS = (
    "case_id",
    "listed_price_before_tax_vnd",
    "discount_pct",
    "discount_amount_vnd",
    "net_price_before_tax_vnd",
    "vat_vnd",
    "contract_price_vnd",
    "maintenance_fee_vnd",
    "total_outflow_vnd",
    "delta_allowed_vnd",
)


def _load_cases() -> list[dict]:
    data = json.loads(DATASET.read_text(encoding="utf-8"))

    def walk(node):
        if isinstance(node, dict):
            return [node] if "case_id" in node else [c for v in node.values() for c in walk(v)]
        if isinstance(node, list):
            return [c for v in node for c in walk(v)]
        return []

    return walk(data)


def test_golden_dataset_available_and_well_formed():
    cases = _load_cases()
    assert len(cases) >= 2, "Cần tối thiểu 2 golden cases (mục tiêu 15 theo ImplementPlan)"
    for case in cases:
        for field in REQUIRED_FIELDS:
            assert field in case, f"{case['case_id']} thiếu trường {field}"
        assert case["delta_allowed_vnd"] == 0, "Golden case phải Exact Match Δ = 0 VNĐ"


def test_golden_cases_hold_accounting_identities():
    for case in _load_cases():
        listed = Decimal(str(case["listed_price_before_tax_vnd"]))
        pct = Decimal(str(case["discount_pct"]))
        discount = listed * pct
        net = listed - discount
        vat = net * VAT_RATE
        contract = net + vat
        maintenance = net * MAINTENANCE_RATE
        total_outflow = contract + maintenance

        assert discount == Decimal(str(case["discount_amount_vnd"])), case["case_id"]
        assert net == Decimal(str(case["net_price_before_tax_vnd"])), case["case_id"]
        assert vat == Decimal(str(case["vat_vnd"])), case["case_id"]
        assert contract == Decimal(str(case["contract_price_vnd"])), case["case_id"]
        assert maintenance == Decimal(str(case["maintenance_fee_vnd"])), case["case_id"]
        assert total_outflow == Decimal(str(case["total_outflow_vnd"])), case["case_id"]
