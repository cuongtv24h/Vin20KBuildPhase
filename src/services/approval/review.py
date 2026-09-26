"""Vòng đời phê duyệt HITL + nguyên tắc SoD (Separation of Duties)."""


class ApprovalService:
    """Quản lý approval intent: submit → review → approve/reject/revision.

    Bất biến bắt buộc: người tạo báo giá KHÔNG ĐƯỢC tự duyệt (SoD —
    vi phạm sinh `SecurityEventType.SOD_VIOLATION_BLOCKED`).
    Duyệt version stale bị chặn (`STALE_VERSION_APPROVAL_BLOCKED`).
    """

    async def submit_for_review(self, quote_id: str, version: int, package: dict) -> dict:
        raise NotImplementedError("C-05: submit for review")

    async def decide(self, intent_id: str, decision: dict) -> dict:
        """Xử lý approve / reject / request-revision từ Manager."""
        raise NotImplementedError("C-05: decide")
