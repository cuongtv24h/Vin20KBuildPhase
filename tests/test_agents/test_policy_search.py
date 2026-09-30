"""Unit test for policy_search tool."""

from unittest.mock import MagicMock, patch

from src.agents.tools.policy_search import search_policy
from src.models.rag_schemas import RetrievedClause


def test_search_policy_tool_returns_formatted_clauses():
    mock_clause = RetrievedClause(
        node_id="POL-02_ART-3_C-1",
        policy_id="POL-02",
        policy_title="Chính sách chiết khấu thanh toán sớm",
        article="Điều 3",
        clause="Khoản 1",
        text="Chiết khấu 8% khi thanh toán sớm bằng vốn tự có.",
        score=0.95,
        valid_from="2025-01-01",
        valid_to="9999-12-31",
    )
    with patch("src.agents.tools.policy_search.get_rag_service") as mock_get_svc:
        mock_svc = MagicMock()
        mock_svc.retrieve.return_value = [mock_clause]
        mock_get_svc.return_value = mock_svc

        result = search_policy.invoke({"query": "chiết khấu thanh toán sớm", "as_of_date": "2025-06-01"})
        assert "POL-02" in result
        assert "Điều 3 Khoản 1" in result
        assert "Chiết khấu 8%" in result
