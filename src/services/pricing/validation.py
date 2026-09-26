"""6 Sanity Check kế toán — node N-11 (khóa theo TD-4.3).

Danh sách này là hợp đồng: Math Engine (C-06) phải thỏa toàn bộ trước khi
kết quả được phép đi tiếp vào ranking (N-12).
"""

SANITY_CHECKS: tuple[str, ...] = (
    "NET_PRICE_POSITIVE",  # (1) Giá Net > 0
    "VAT_RATE_CORRECT",  # (2) Thuế VAT tính đúng tỷ lệ trên Giá Net
    "MAINTENANCE_FEE_CORRECT",  # (3) KPBT tính đúng trên Giá Net
    "INSTALLMENTS_SUM_EQUALS_CONTRACT",  # (4) Tổng các đợt ≡ P_contract
    "NO_INTERMEDIATE_ROUNDING",  # (5) Không làm tròn số trung gian
    "FIRST_INSTALLMENT_AFTER_DEPOSIT_OFFSET",  # (6) Đợt 1 nộp đúng sau cấn trừ cọc
)


def run_sanity_checks(pricing_output: dict) -> dict:
    """Thực thi 6 check; trả về {check_name: passed} + overall verdict."""
    raise NotImplementedError("C-06/N-11: sanity checks")
