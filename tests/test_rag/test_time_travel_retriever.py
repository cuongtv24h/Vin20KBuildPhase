"""Unit tests for TimeTravelPolicyRetriever."""

from datetime import date

from llama_index.core.schema import TextNode

from src.models.rag_schemas import TimeTravelFilter
from src.rag.retriever.time_travel_retriever import TimeTravelPolicyRetriever


def test_time_travel_filters():
    # Setup test nodes with temporal bounds
    node_active = TextNode(
        id_="node_active",
        text="Chính sách chiết khấu 8% thanh toán sớm 95%",
        metadata={
            "policy_id": "POL-2026-EARLY",
            "policy_name": "Chính sách 2026",
            "article": "Điều 1",
            "clause": "Khoản 1",
            "valid_from": "2026-01-01",
            "valid_to": "2026-06-30",
            "applicable_units": ["1BR", "2BR", "3BR"],
        },
    )

    node_expired = TextNode(
        id_="node_expired",
        text="Chính sách năm 2025 đã hết hạn chiết khấu 10%",
        metadata={
            "policy_id": "POL-2025-OLD",
            "policy_name": "Chính sách 2025",
            "article": "Điều 1",
            "clause": "Khoản 1",
            "valid_from": "2025-01-01",
            "valid_to": "2025-12-31",
            "applicable_units": ["ALL"],
        },
    )

    retriever = TimeTravelPolicyRetriever(nodes=[node_active, node_expired])

    # 1. Search during 2026-03-15 (node_active should match, node_expired excluded)
    filter_2026 = TimeTravelFilter(
        transaction_date=date(2026, 3, 15),
        service_code="2BR",
    )
    results_2026 = retriever.retrieve("chiết khấu", time_filter=filter_2026)
    assert len(results_2026) == 1
    assert results_2026[0].policy_id == "POL-2026-EARLY"

    # 2. Search during 2025-06-01 (node_expired should match, node_active excluded)
    filter_2025 = TimeTravelFilter(
        transaction_date=date(2025, 6, 1),
    )
    results_2025 = retriever.retrieve("chiết khấu", time_filter=filter_2025)
    assert len(results_2025) == 1
    assert results_2025[0].policy_id == "POL-2025-OLD"

    # 3. Search in 2027 (both should be excluded as both are expired)
    filter_2027 = TimeTravelFilter(
        transaction_date=date(2027, 1, 1),
    )
    results_2027 = retriever.retrieve("chiết khấu", time_filter=filter_2027)
    assert len(results_2027) == 0
