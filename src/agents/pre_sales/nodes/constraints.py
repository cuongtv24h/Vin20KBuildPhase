"""Node trích xuất & xác nhận ràng buộc tài chính (F2)."""

from src.agents.pre_sales.state import PreSalesSessionState


async def extract_constraints_node(state: PreSalesSessionState) -> dict:
    """F2 — Constraint Extraction.

    Trích xuất ràng buộc chuẩn hóa (ngân sách tối đa, % vốn tự có, mức trả
    tháng chấp nhận được, nhu cầu nhận nhà...) từ transcript.
    """
    raise NotImplementedError("C-09/F2: constraint extraction node")


async def confirm_constraints_node(state: PreSalesSessionState) -> dict:
    """Xác nhận ràng buộc với khách trước khi tính phương án tham khảo."""
    raise NotImplementedError("C-09/F2: constraint confirmation node")
