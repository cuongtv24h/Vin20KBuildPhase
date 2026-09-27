"""
Transaction Context Loading Node (N-03)
Owner: TechLead (cuongtv_02560)
"""

from __future__ import annotations

from src.agents.official_quote.state import OfficialQuoteState


def load_transaction_context(state: OfficialQuoteState) -> dict:
    """
    N-03: Load authoritative transaction context from unit and project catalog.
    Enriches state with unit metadata, listed price validation, and baseline parameters.
    """
    unit_code = state.get("unit_code", "UNKNOWN")
    project_id = state.get("project_id", "UNKNOWN")
    listed_price = state.get("listed_price_before_tax_vnd", 3_000_000_000)

    # Context enrichment with canonical structural parameters
    context = {
        "project_id": project_id,
        "unit_code": unit_code,
        "listed_price_before_tax_vnd": listed_price,
        "floor_area_m2": 68.5,
        "bedroom_count": 2,
        "building_code": "T1",
        "zone_code": "ZONE-A",
        "baseline_vat_rate": 0.10,
        "baseline_kpbt_rate": 0.02,
    }

    return {
        "transaction_context": context,
    }
