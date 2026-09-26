"""Đóng băng snapshot chính sách tại thời điểm giao dịch.

Snapshot là căn cứ pháp lý khi có tranh chấp: báo giá đã phát hành phải luôn
kiểm chứng được ngược lại chính sách hợp lệ lúc phát hành, bất kể chính sách
đã thay đổi bao nhiêu lần về sau (time-travel versioning).
"""


class PolicySnapshotService:
    """Freeze + lookup snapshot theo (transaction_date, project_id)."""

    async def freeze(self, transaction_date: str, project_id: str, policy_ids: list[str]) -> dict:
        """Tạo snapshot bất biến, trả về `policy_snapshot_hash` (N-04)."""
        raise NotImplementedError("C-02: freeze snapshot")

    async def resolve(self, snapshot_hash: str) -> dict:
        """Đọc lại snapshot theo hash — phục vụ audit & verify (C-07)."""
        raise NotImplementedError("C-02: resolve snapshot")
