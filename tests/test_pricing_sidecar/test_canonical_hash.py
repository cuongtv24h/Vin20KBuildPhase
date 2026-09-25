"""Unit tests for RFC 8785 Canonical JSON (JCS) Serializer and SHA-256 Hash Generator.

Tests cover:
1. RFC 8785 key sorting (UTF-16 code units, BMP and non-BMP surrogate pairs, Vietnamese Unicode).
2. Whitespace elimination (no whitespace outside strings).
3. Data types handling: int, bool, None, Decimal (integer VND vs rates), Enum, date/datetime.
4. Anti-Float Guard enforcement (raises TypeError on float in any depth).
5. Determinism invariance (identical output regardless of dict insertion order).
6. Tamper detection sensitivity.
7. Hash format and verification (verify_canonical_hash).
8. Snapshot payload builder & PricingCalculationOutput factory (FCS v2.6 §8).
9. Performance SLA verification (< 5ms).
"""

import time
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from src.pricing_sidecar.canonical_hash import (
    CANONICAL_ENGINE_VERSION,
    CANONICAL_SPEC_VERSION,
    _jcs_utf16_sort_key,
    build_pricing_snapshot_payload,
    canonical_json_bytes,
    canonical_json_dumps,
    create_pricing_calculation_output,
    generate_canonical_hash,
    verify_canonical_hash,
)
from src.pricing_sidecar.contracts import (
    OptimizationObjective,
    PricingCalculationInput,
    PricingCalculationOutput,
    ScenarioType,
)
from src.pricing_sidecar.engine import (
    calculate_canonical_scenario,
    calculate_pa_chudong,
    calculate_pa_nhanh,
    calculate_pa_vay,
)
from src.pricing_sidecar.ranking import recommend_best_scenario


class TestRFC8785KeySorting:
    """Tests for UTF-16 code unit dictionary key sorting according to RFC 8785 §3.2.3."""

    def test_simple_dict_keys_sorted(self) -> None:
        raw = {"z": 1, "b": 2, "a": 3, "m": 4}
        canonical = canonical_json_dumps(raw)
        assert canonical == '{"a":3,"b":2,"m":4,"z":1}'

    def test_nested_dict_keys_sorted_recursively(self) -> None:
        raw = {
            "outer_z": {"inner_b": 1, "inner_a": 2},
            "outer_a": {"y": 10, "x": 20},
        }
        canonical = canonical_json_dumps(raw)
        assert canonical == '{"outer_a":{"x":20,"y":10},"outer_z":{"inner_a":2,"inner_b":1}}'

    def test_utf16_surrogate_pair_vs_bmp_sorting(self) -> None:
        """RFC 8785 §3.2.3 requires sorting by UTF-16 code units.

        Emoji U+1F600 has code point 128512, encoded in UTF-16 as surrogate pair
        (0xD83D, 0xDE00). Character U+E000 has code point 57344, encoded as 0xE000.
        By UTF-16 code units: 0xD83D < 0xE000, so emoji MUST sort BEFORE U+E000!
        """
        emoji_key = "\U0001f600"
        bmp_pua_key = "\ue000"
        assert _jcs_utf16_sort_key(emoji_key) < _jcs_utf16_sort_key(bmp_pua_key)

        data = {bmp_pua_key: "bmp", emoji_key: "emoji"}
        serialized = canonical_json_dumps(data)
        expected = f'{{"{emoji_key}":"emoji","{bmp_pua_key}":"bmp"}}'
        assert serialized == expected

    def test_vietnamese_unicode_keys_sorting(self) -> None:
        data = {
            "Đợt 3": 3,
            "Đợt 1": 1,
            "Cọc": 100,
            "Bàn giao": 8,
            "An ninh": 0,
        }
        serialized = canonical_json_dumps(data)
        # Expected UTF-16 order: ASCII 'A', 'B', 'C' come before 'Đ' (U+0110)
        assert serialized.startswith('{"An ninh":0,"Bàn giao":8,"Cọc":100,"Đợt 1":1,"Đợt 3":3}')


class TestWhitespaceAndMinification:
    """Tests confirming zero whitespace outside string literals."""

    def test_no_whitespace_outside_strings(self) -> None:
        data = {
            "title": "Báo giá căn hộ A-12-05",
            "items": [1, 2, 3],
            "nested": {"active": True, "value": None},
        }
        res = canonical_json_dumps(data)
        # Ensure no spaces outside quotes
        assert " " not in res.replace("Báo giá căn hộ A-12-05", "")
        assert "\n" not in res
        assert "\t" not in res
        assert ": " not in res
        assert ", " not in res


class TestDataTypeCanonicalization:
    """Tests for zero-float type conversions: Decimal VND vs rates, Enum, Date."""

    def test_decimal_integer_vnd_becomes_int(self) -> None:
        data = {"listed_price_vnd": Decimal("3500000000"), "deposit_vnd": Decimal("100000000.00")}
        dumped = canonical_json_dumps(data)
        assert dumped == '{"deposit_vnd":100000000,"listed_price_vnd":3500000000}'

    def test_decimal_fractional_rate_becomes_str(self) -> None:
        data = {"vat_rate": Decimal("0.1000"), "kpbt_rate": Decimal("0.0200")}
        dumped = canonical_json_dumps(data)
        assert dumped == '{"kpbt_rate":"0.0200","vat_rate":"0.1000"}'

    def test_booleans_and_none(self) -> None:
        data = {"is_handover": True, "is_reconciliation": False, "extra_note": None}
        dumped = canonical_json_dumps(data)
        assert dumped == '{"extra_note":null,"is_handover":true,"is_reconciliation":false}'

    def test_enum_handling(self) -> None:
        data = {
            "scenario": ScenarioType.STANDARD_PROGRESS,
            "objective": OptimizationObjective.MIN_NET_PRICE,
        }
        dumped = canonical_json_dumps(data)
        assert dumped == '{"objective":"MIN_NET_PRICE","scenario":"STANDARD_PROGRESS"}'

    def test_date_and_datetime(self) -> None:
        d = date(2026, 3, 15)
        dt = datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC)
        data = {"contract_date": d, "timestamp": dt}
        dumped = canonical_json_dumps(data)
        assert '"contract_date":"2026-03-15"' in dumped
        assert '"timestamp":"2026-03-15T12:00:00+00:00"' in dumped

    def test_list_and_tuple_order_preserved(self) -> None:
        data = {"sequence": [3, 1, 2], "tuple_seq": (10, 5, 20)}
        dumped = canonical_json_dumps(data)
        assert dumped == '{"sequence":[3,1,2],"tuple_seq":[10,5,20]}'


class TestAntiFloatGuardEnforcement:
    """Tests ensuring Anti-Float Guard prevents any float in canonical serialization."""

    def test_float_in_top_level_dict_rejected(self) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            canonical_json_dumps({"price": 3500000000.0})

    def test_float_in_nested_list_rejected(self) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            canonical_json_dumps({"items": [1, 2, 3.14]})

    def test_float_in_deeply_nested_dict_rejected(self) -> None:
        with pytest.raises(TypeError, match="FLOAT_PROHIBITED"):
            canonical_json_dumps({"level1": {"level2": {"rate": 0.08}}})


class TestDeterminismAndInvariance:
    """Tests proving identical canonical bytes and hashes regardless of insertion order."""

    def test_dict_insertion_order_invariance(self) -> None:
        dict_1 = {"alpha": 1, "beta": 2, "gamma": 3, "delta": 4}
        dict_2 = {"delta": 4, "gamma": 3, "alpha": 1, "beta": 2}
        dict_3 = {"beta": 2, "alpha": 1, "delta": 4, "gamma": 3}

        # Serialized strings must be identical
        s1 = canonical_json_dumps(dict_1)
        s2 = canonical_json_dumps(dict_2)
        s3 = canonical_json_dumps(dict_3)
        assert s1 == s2 == s3

        # SHA-256 hashes must be identical
        h1 = generate_canonical_hash(dict_1)
        h2 = generate_canonical_hash(dict_2)
        h3 = generate_canonical_hash(dict_3)
        assert h1 == h2 == h3

    def test_canonical_json_bytes_utf8(self) -> None:
        data = {"unit": "Căn A-12-05", "price": 3500000000}
        b = canonical_json_bytes(data)
        assert isinstance(b, bytes)
        assert b == '{"price":3500000000,"unit":"Căn A-12-05"}'.encode()


class TestTamperDetectionAndVerification:
    """Tests verifying hash integrity and tamper-evidence."""

    def test_sha256_hash_format(self) -> None:
        data = {"unit_code": "A-12-05", "net_price_vnd": 3500000000}
        h = generate_canonical_hash(data)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_tamper_amount_changes_hash(self) -> None:
        original = {"unit_code": "A-12-05", "net_price_vnd": 3500000000}
        tampered = {"unit_code": "A-12-05", "net_price_vnd": 3500000001}  # Changed 1 VND
        h_orig = generate_canonical_hash(original)
        h_tamp = generate_canonical_hash(tampered)
        assert h_orig != h_tamp

    def test_tamper_unit_code_changes_hash(self) -> None:
        original = {"unit_code": "A-12-05", "net_price_vnd": 3500000000}
        tampered = {"unit_code": "A-12-06", "net_price_vnd": 3500000000}
        assert generate_canonical_hash(original) != generate_canonical_hash(tampered)

    def test_verify_canonical_hash(self) -> None:
        data = {"key": "value", "count": 42}
        correct_hash = generate_canonical_hash(data)

        # Exact match
        assert verify_canonical_hash(data, correct_hash) is True
        # Case insensitive match
        assert verify_canonical_hash(data, correct_hash.upper()) is True
        # Altered hash fails
        assert verify_canonical_hash(data, "0" * 64) is False
        # Invalid length fails
        assert verify_canonical_hash(data, "abc") is False
        assert verify_canonical_hash(data, "") is False


class TestFCSSection8SnapshotIntegration:
    """Tests integrating with FCS v2.6 §8 snapshot specification."""

    @pytest.fixture
    def standard_input(self) -> PricingCalculationInput:
        return PricingCalculationInput(
            unit_code="A-12-05",
            listed_price_vnd=3500000000,
            deposit_amount_vnd=100000000,
            deposit_date=date(2026, 3, 8),
            contract_signing_date=date(2026, 3, 15),
            resolved_policy_snapshot_id="SNAP-2026-03-15-V1",
            source_policy_hash="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )

    def test_build_pricing_snapshot_payload_structure(self, standard_input: PricingCalculationInput) -> None:
        res_chudong = calculate_pa_chudong(
            listed_price_vnd=standard_input.listed_price_vnd,
            deposit_amount_vnd=standard_input.deposit_amount_vnd,
            deposit_date=standard_input.deposit_date,
        )
        res_nhanh = calculate_pa_nhanh(
            listed_price_vnd=standard_input.listed_price_vnd,
            deposit_amount_vnd=standard_input.deposit_amount_vnd,
            deposit_date=standard_input.deposit_date,
        )
        res_vay = calculate_pa_vay(
            listed_price_vnd=standard_input.listed_price_vnd,
            deposit_amount_vnd=standard_input.deposit_amount_vnd,
            deposit_date=standard_input.deposit_date,
        )
        scenario_results = [res_chudong, res_nhanh, res_vay]

        rec = recommend_best_scenario(
            scenarios=scenario_results,
            objective=OptimizationObjective.MIN_INITIAL_OUTFLOW,
        )

        payload = build_pricing_snapshot_payload(
            input_data=standard_input,
            scenario_results=scenario_results,
            recommended_result=rec,
        )

        # Verify required FCS §8 keys
        assert payload["spec_version"] == CANONICAL_SPEC_VERSION
        assert payload["engine_version"] == CANONICAL_ENGINE_VERSION
        assert payload["input_context"]["unit_code"] == "A-12-05"
        assert payload["input_context"]["listed_price_vnd"] == 3500000000
        assert payload["input_context"]["deposit_amount_vnd"] == 100000000
        assert len(payload["scenario_summaries"]) == 3
        assert payload["recommended_scenario"] == "STANDARD_PROGRESS"
        assert payload["objective"] == "MIN_INITIAL_OUTFLOW"

    def test_create_pricing_calculation_output_factory(self, standard_input: PricingCalculationInput) -> None:
        res_chudong = calculate_canonical_scenario(
            scenario_type_or_code=ScenarioType.STANDARD_PROGRESS,
            listed_price_vnd=standard_input.listed_price_vnd,
            deposit_amount_vnd=standard_input.deposit_amount_vnd,
            deposit_date=standard_input.deposit_date,
        )
        res_nhanh = calculate_canonical_scenario(
            scenario_type_or_code=ScenarioType.EARLY_95,
            listed_price_vnd=standard_input.listed_price_vnd,
            deposit_amount_vnd=standard_input.deposit_amount_vnd,
            deposit_date=standard_input.deposit_date,
        )
        res_vay = calculate_canonical_scenario(
            scenario_type_or_code=ScenarioType.BANK_LOAN_HTLS,
            listed_price_vnd=standard_input.listed_price_vnd,
            deposit_amount_vnd=standard_input.deposit_amount_vnd,
            deposit_date=standard_input.deposit_date,
        )
        results = [res_chudong, res_nhanh, res_vay]
        rec = recommend_best_scenario(results, OptimizationObjective.MIN_NET_PRICE)

        output: PricingCalculationOutput = create_pricing_calculation_output(
            input_data=standard_input,
            scenario_results=results,
            recommended_result=rec,
            quote_id="Q-2026-03-001",
            quote_version=1,
        )

        # Pydantic validation passes
        assert output.spec_version == "2.6"
        assert output.unit_code == "A-12-05"
        assert output.quote_id == "Q-2026-03-001"
        assert output.quote_version == 1
        assert len(output.canonical_snapshot_hash) == 64

        # Validate that hash matches the regenerated snapshot payload
        rebuilt_payload = build_pricing_snapshot_payload(
            input_data=standard_input,
            scenario_results=results,
            recommended_result=rec,
        )
        assert verify_canonical_hash(rebuilt_payload, output.canonical_snapshot_hash) is True


class TestPerformanceSLA:
    """Benchmark tests ensuring hash generation latency meets strict performance SLA."""

    def test_hash_generation_latency_under_5ms(self) -> None:
        payload = {
            "spec_version": "2.6",
            "engine_version": "DeterministicPricingEngine_v2.6",
            "unit_code": "A-12-05",
            "listed_price_vnd": 3500000000,
            "scenarios": [
                {"scenario": "STANDARD_PROGRESS", "net": 3500000000, "contract": 3920000000},
                {"scenario": "EARLY_95", "net": 3220000000, "contract": 3606400000},
                {"scenario": "BANK_LOAN_HTLS", "net": 3500000000, "contract": 3920000000},
            ],
            "recommended": "EARLY_95",
        }

        # Warm-up run
        generate_canonical_hash(payload)

        # Benchmark 100 iterations
        start = time.perf_counter()
        iterations = 100
        for _ in range(iterations):
            generate_canonical_hash(payload)
        elapsed_sec = time.perf_counter() - start
        avg_ms = (elapsed_sec / iterations) * 1000

        # SLA requires < 5ms per hash generation
        assert avg_ms < 5.0, f"Average latency {avg_ms:.3f}ms exceeds SLA limit of 5.0ms"
