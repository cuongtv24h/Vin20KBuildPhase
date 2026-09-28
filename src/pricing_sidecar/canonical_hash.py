"""RFC 8785 Canonical JSON (JCS) Serializer and SHA-256 Hash Generator.

FCS v2.6 Reference: Section 8 (Canonical Snapshot Hash & RFC 8785 JCS)
TD-4.1 Reference: Section Spike 2 (RFC 8785 Canonical JSON & Provider Adapters)
TD-4.4 Reference: Hash Verification & Audit Evidence Integrity

This module provides:
1. `_jcs_utf16_sort_key`: UTF-16 code units sorting for dictionary keys (RFC 8785 §3.2.3).
2. `canonicalize_data`: Recursive normalization preserving Zero-Float invariants.
3. `canonical_json_dumps`: RFC 8785 Canonical JSON string serializer.
4. `canonical_json_bytes`: RFC 8785 UTF-8 encoded bytes.
5. `generate_canonical_hash`: 64-hex lowercase SHA-256 hash calculation.
6. `verify_canonical_hash`: Cryptographic tamper-evidence verification.
7. `build_pricing_snapshot_payload`: FCS §8 canonical snapshot payload generator.
8. `create_pricing_calculation_output`: Factory producing signed PricingCalculationOutput.
"""

import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel

from src.pricing_sidecar.arithmetic import assert_no_float
from src.pricing_sidecar.contracts import (
    PricingCalculationInput,
    PricingCalculationOutput,
    RecommendationResult,
    ScenarioCalculationResult,
    ValidationReport,
)

# Canonical Specification Constants
CANONICAL_SPEC_VERSION: str = "2.6"
CANONICAL_ENGINE_VERSION: str = "DeterministicPricingEngine_v2.6"


def _jcs_utf16_sort_key(key: str) -> bytes:
    """Extract sorting key based on UTF-16 code units according to RFC 8785 §3.2.3.

    In RFC 8785, dictionary keys MUST be sorted in ascending order of their
    UTF-16 code units. In Python, encoding a string as 'utf-16-be' produces
    a byte sequence where lexicographical comparison matches UTF-16 code unit
    numerical order, including surrogate pairs for characters outside BMP.
    """
    return key.encode("utf-16-be")


def canonicalize_data(obj: Any) -> Any:
    """Recursively normalize any Python data structure for RFC 8785 serialization.

    Guarantees:
    - Enforces Anti-Float Guard: raises TypeError if any float is encountered.
    - Resolves Pydantic BaseModels into dictionaries.
    - Sorts dictionary keys according to RFC 8785 UTF-16 code unit order.
    - Preserves list and tuple orders while recursively canonicalizing children.
    - Converts integer Decimals to int (accounting VND amounts).
    - Converts fractional Decimals to str (rates, ratios).
    - Converts Enums to their primitive values.
    - Converts date and datetime instances to standard ISO-8601 strings.
    """
    # Enforce Anti-Float Guard
    assert_no_float(obj)

    if isinstance(obj, BaseModel):
        obj = obj.model_dump(mode="python")

    if isinstance(obj, dict):
        # Recursively process items and sort by RFC 8785 UTF-16 code units
        processed_items: list[tuple[str, Any]] = []
        for k, v in obj.items():
            str_key = str(k)
            processed_items.append((str_key, canonicalize_data(v)))
        # Sort items deterministically
        processed_items.sort(key=lambda item: _jcs_utf16_sort_key(item[0]))
        return dict(processed_items)

    if isinstance(obj, (list, tuple)):
        return [canonicalize_data(item) for item in obj]

    if isinstance(obj, set):
        # Sets have no deterministic order, sort by string representation
        normalized_elements = [canonicalize_data(item) for item in obj]
        normalized_elements.sort(key=lambda x: str(x))
        return normalized_elements

    # Check bool before int because bool is a subclass of int in Python
    if isinstance(obj, bool):
        return obj

    if isinstance(obj, int):
        return obj

    if isinstance(obj, Decimal):
        # Integer VND accounting amount -> int; Fractional rate -> str
        if obj % 1 == 0:
            return int(obj)
        return str(obj)

    if isinstance(obj, Enum):
        return obj.value

    if isinstance(obj, (date, datetime)):
        return obj.isoformat()

    if isinstance(obj, str):
        return obj

    if obj is None:
        return None

    # Fallback to string representation for other unhandled primitives
    return str(obj)


def canonical_json_dumps(data: Any) -> str:
    """Serialize data into an RFC 8785 Canonical JSON string.

    Specifications:
    - No whitespace outside string literals: separators=(',', ':').
    - Object keys recursively sorted by UTF-16 code unit ordering.
    - Direct UTF-8 representation without unnecessary ASCII escapes.
    """
    normalized = canonicalize_data(data)
    return json.dumps(normalized, separators=(",", ":"), ensure_ascii=False)


def canonical_json_bytes(data: Any) -> bytes:
    """Serialize data into RFC 8785 Canonical JSON UTF-8 encoded bytes."""
    return canonical_json_dumps(data).encode("utf-8")


def generate_canonical_hash(data: Any) -> str:
    """Calculate the deterministic SHA-256 hash of canonicalized JSON payload.

    Returns:
        A 64-character lowercase hexadecimal string matching `^[0-9a-f]{64}$`.
    """
    raw_bytes = canonical_json_bytes(data)
    return hashlib.sha256(raw_bytes).hexdigest().lower()


def verify_canonical_hash(data: Any, expected_hash: str) -> bool:
    """Verify that data produces the expected SHA-256 canonical hash.

    Args:
        data: The payload data to inspect.
        expected_hash: The 64-character hex hash to compare against.

    Returns:
        True if hashes match identically (case-insensitive), False otherwise.
    """
    if not expected_hash or len(expected_hash.strip()) != 64:
        return False
    computed_hash = generate_canonical_hash(data)
    return computed_hash.lower() == expected_hash.strip().lower()


def build_pricing_snapshot_payload(
    input_data: PricingCalculationInput,
    scenario_results: list[ScenarioCalculationResult],
    recommended_result: RecommendationResult | None = None,
    *,
    spec_version: str = CANONICAL_SPEC_VERSION,
    engine_version: str = CANONICAL_ENGINE_VERSION,
    resolved_policy_snapshot_id: str | None = None,
    source_policy_hash: str | None = None,
) -> dict[str, Any]:
    """Construct canonical snapshot payload conforming to FCS v2.6 §8.

    Covers transaction context, policy sources, and summarized scenario results.
    """
    # Build scenario summaries in canonical structure
    summaries: list[dict[str, Any]] = []
    for s in scenario_results:
        scenario_code = s.scenario_type.value if hasattr(s.scenario_type, "value") else str(s.scenario_type)
        summaries.append(
            {
                "scenario_type": scenario_code,
                "net_price_vnd": int(s.net_price_before_vat),
                "contract_price_vnd": int(s.final_contract_price),
                "initial_gross_vnd": int(s.initial_gross_obligation_vnd),
                "initial_outflow_vnd": int(s.initial_cash_outflow_vnd),
                "cash_to_handover_vnd": int(s.customer_cash_outflow_until_handover),
            }
        )

    # Determine recommended scenario code and objective
    rec_scenario = (
        recommended_result.recommended_scenario
        if recommended_result
        else (summaries[0]["scenario_type"] if summaries else "STANDARD_PROGRESS")
    )
    rec_objective = recommended_result.selected_objective if recommended_result else "MIN_INITIAL_OUTFLOW"

    resolved_snapshot = (
        resolved_policy_snapshot_id
        or getattr(input_data, "resolved_policy_snapshot_id", None)
        or getattr(input_data, "policy_snapshot_id", None)
        or "SNAP-CANONICAL-V1"
    )
    resolved_policy_hash = (
        source_policy_hash
        or getattr(input_data, "source_policy_hash", None)
        or "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    )

    payload: dict[str, Any] = {
        "spec_version": spec_version,
        "engine_version": engine_version,
        "input_context": {
            "unit_code": input_data.unit_code,
            "listed_price_vnd": int(input_data.listed_price_vnd),
            "deposit_amount_vnd": int(input_data.deposit_amount_vnd),
            "deposit_date": input_data.deposit_date.isoformat(),
            "contract_signing_date": input_data.contract_signing_date.isoformat(),
            "resolved_policy_snapshot_id": resolved_snapshot,
            "source_policy_hash": resolved_policy_hash,
            "tax_vat_rate": str(input_data.tax_vat_rate),
            "maintenance_fee_rate": str(input_data.maintenance_fee_rate),
            "max_discount_rate": str(input_data.max_discount_rate),
            "max_total_discount_cap_rate": str(input_data.max_total_discount_cap_rate),
        },
        "scenario_summaries": summaries,
        "recommended_scenario": rec_scenario,
        "objective": rec_objective,
    }

    return payload


def create_pricing_calculation_output(
    input_data: PricingCalculationInput,
    scenario_results: list[ScenarioCalculationResult],
    recommended_result: RecommendationResult | None = None,
    validation_report: ValidationReport | None = None,
    *,
    quote_id: str | None = None,
    quote_version: int | None = None,
    spec_version: str = CANONICAL_SPEC_VERSION,
    engine_version: str = CANONICAL_ENGINE_VERSION,
    calculation_timestamp: str | None = None,
) -> PricingCalculationOutput:
    """Factory creating fully populated and cryptographically signed PricingCalculationOutput."""
    if calculation_timestamp is None:
        calculation_timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    if validation_report is None:
        validation_report = ValidationReport()

    # Construct canonical snapshot payload per FCS §8 and generate SHA-256 hash
    snapshot_payload = build_pricing_snapshot_payload(
        input_data=input_data,
        scenario_results=scenario_results,
        recommended_result=recommended_result,
        spec_version=spec_version,
        engine_version=engine_version,
    )
    snapshot_hash = generate_canonical_hash(snapshot_payload)

    return PricingCalculationOutput(
        spec_version=spec_version,
        engine_version=engine_version,
        calculation_timestamp=calculation_timestamp,
        unit_code=input_data.unit_code,
        scenario_results=scenario_results,
        recommended_result=recommended_result,
        validation_report=validation_report,
        canonical_snapshot_hash=snapshot_hash,
        quote_id=quote_id,
        quote_version=quote_version,
    )
