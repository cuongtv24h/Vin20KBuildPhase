"""Dual Reconciliation — đối soát chéo 2 đường tính, bắt buộc Δ = 0 VNĐ."""


def reconcile(primary: dict, secondary: dict) -> dict:
    """Đối soát 2 kết quả tính độc lập; lệch dù chỉ 1 VNĐ → FAIL toàn bộ lượt tính.

    Returns:
        {reconciled: bool, delta_vnd: str("0"), mismatch_fields: [...]}
    """
    raise NotImplementedError("C-06: dual reconciliation")
