"""Policy Search Tool for LangGraph Agents.

Exposes TimeTravelPolicyRetriever and PolicyRAGService as a callable tool for
Pre-Sales and Official Quote agents.
"""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from src.services.rag.service import PolicyRAGService

logger = logging.getLogger(__name__)

# Lazy singleton
_rag_service: PolicyRAGService | None = None


def get_rag_service() -> PolicyRAGService:
    """Gets or initializes the PolicyRAGService singleton."""
    global _rag_service
    if _rag_service is None:
        _rag_service = PolicyRAGService()
    return _rag_service


@tool
def search_policy(query: str, as_of_date: str | None = None, top_k: int = 5) -> str:
    """Tra cứu chính sách bán hàng và bằng chứng pháp lý (C-02/C-03).

    Hỗ trợ tìm kiếm ngữ nghĩa kết hợp lọc ngày hiệu lực (Time-Travel).

    Args:
        query: Câu hỏi hoặc từ khóa cần tra cứu (ví dụ: "chiết khấu thanh toán sớm Vinhomes")
        as_of_date: Ngày hiệu lực cần tra cứu (định dạng YYYY-MM-DD, mặc định là ngày hôm nay)
        top_k: Số lượng kết quả tối đa

    Returns:
        Văn bản tổng hợp các điều khoản chính sách phù hợp cùng tọa độ bằng chứng.
    """
    try:
        service = get_rag_service()
        clauses = service.retrieve(
            query=query,
            as_of_date=as_of_date,
            top_k=top_k,
        )
        if not clauses:
            return f"Không tìm thấy điều khoản chính sách nào phù hợp với câu hỏi: '{query}' tại thời điểm {as_of_date or 'hiện tại'}."

        output_lines = [f"Tìm thấy {len(clauses)} điều khoản phù hợp:"]
        for idx, clause in enumerate(clauses, 1):
            coord = f"[{clause.policy_id} - {clause.article or ''} {clause.clause or ''}]".strip()
            score_str = f"Score: {clause.score:.3f}" if clause.score else ""
            output_lines.append(f"{idx}. {coord} ({score_str})")
            output_lines.append(f"   {clause.text.strip()}")

        return "\n".join(output_lines)
    except Exception as e:
        logger.error(f"Error in search_policy tool: {e}", exc_info=True)
        return f"Lỗi khi tra cứu chính sách: {str(e)}"


# Alias per CodeBaseIndex.md Section 4.2
policy_time_travel_search = search_policy

__all__ = [
    "get_rag_service",
    "search_policy",
    "policy_time_travel_search",
]
