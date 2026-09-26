"""Tool tra cứu chính sách time-travel cho cả hai StateGraph (C-02)."""

from datetime import date

from langchain_core.tools import tool


@tool
def policy_time_travel_search(query: str, transaction_date: date, project_id: str) -> str:
    """Tra cứu điều khoản chính sách CÓ HIỆU LỰC tại ngày giao dịch.

    Chỉ trả về chunk từ phiên bản policy đang effective (Time-Travel SQL Filter),
    kèm tọa độ nguồn phục vụ evidence linking (F4).

    Args:
        query: Câu truy vấn ngữ nghĩa (ví dụ: "chiết khấu thanh toán sớm 95%")
        transaction_date: Ngày giao dịch để lọc phiên bản hiệu lực
        project_id: ID dự án (ví dụ: PROJECT-VLF-001)

    Returns:
        Danh sách chunk kèm metadata (policy_id, version, tọa độ, hash)
    """
    raise NotImplementedError("C-02: gọi src.services.rag.retrieval.TimeTravelPolicyRetriever")
