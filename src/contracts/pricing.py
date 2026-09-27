"""
Pricing contracts for UDS Sidecar communication and Scenario modeling.
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from src.contracts.enums import OptimizationObjective


class ScenarioCode(StrEnum):
    """Mã định danh 3 phương án tài chính chuẩn tắc."""
    PA_CHUDONG = "PA-CHUDONG"
    PA_NHANH = "PA-NHANH"
    PA_VAY = "PA-VAY"


class PaymentScheduleItem(BaseModel):
    """Chi tiết 1 đợt thanh toán trong kế hoạch tài chính."""
    installment_number: int = Field(..., ge=1, description="Số thứ tự đợt thanh toán")
    due_milestone: str = Field(..., description="Mô tả mốc thời hạn thanh toán")
    percentage: float = Field(..., ge=0.0, le=100.0, description="Tỷ lệ thanh toán (%)")
    amount_vnd: int = Field(..., ge=0, description="Số tiền thanh toán đợt này (VNĐ)")
    vat_vnd: int = Field(default=0, ge=0, description="Tiền thuế VAT (VNĐ)")
    kpbt_vnd: int = Field(default=0, ge=0, description="Kinh phí bảo trì 2% (VNĐ)")
    net_amount_vnd: int = Field(..., ge=0, description="Số tiền gốc chưa VAT/KPBT (VNĐ)")


class ScenarioDetail(BaseModel):
    """Chi tiết kết quả tính toán của 1 phương án tài chính."""
    scenario_code: ScenarioCode = Field(..., description="Mã phương án: PA-CHUDONG, PA-NHANH, PA-VAY")
    scenario_name: str = Field(..., description="Tên phương án hiển thị")
    net_price_vnd: int = Field(..., ge=0, description="Giá mua Net trước thuế (VNĐ)")
    vat_vnd: int = Field(..., ge=0, description="Thuế VAT 10% (VNĐ)")
    kpbt_vnd: int = Field(..., ge=0, description="Kinh phí bảo trì 2% (VNĐ)")
    total_contract_price_vnd: int = Field(..., ge=0, description="Tổng giá trị hợp đồng gồm VAT và KPBT (VNĐ)")
    initial_cash_outflow_vnd: int = Field(..., ge=0, description="Số tiền mặt cần chuẩn bị Đợt 1 (VNĐ)")
    monthly_burden_vnd: int = Field(..., ge=0, description="Nghĩa vụ chi trả bình quân hàng tháng (VNĐ)")
    total_cash_outflow_vnd: int = Field(..., ge=0, description="Tổng dòng tiền mặt tự chi trả đến khi nhận nhà (VNĐ)")
    benefit_value_vnd: int = Field(..., ge=0, description="Tổng giá trị quà tặng, voucher quy đổi (VNĐ)")
    payment_schedule: list[PaymentScheduleItem] = Field(default_factory=list, description="Kế hoạch dòng tiền các đợt")
    applied_incentives: list[str] = Field(default_factory=list, description="Danh sách ưu đãi chiết khấu áp dụng")
    is_feasible: bool = Field(default=True, description="Kịch bản có khả thi theo năng lực ngân sách khách hàng")


class PricingInput(BaseModel):
    """Dữ liệu đầu vào gửi sang Pricing Sidecar UDS."""
    schema_version: str = Field(default="pricing-input.v1")
    execution_context: str = Field(default="PRE_SALES", description="PRE_SALES hoặc OFFICIAL_QUOTE")
    quote_id: str | None = None
    quote_version: int | None = None
    project_id: str
    unit_code: str
    listed_price_before_tax_vnd: int = Field(..., gt=0)
    transaction_date: str = Field(..., description="Định dạng YYYY-MM-DD")
    own_funds_vnd: int = Field(..., ge=0, description="Ngân sách tự có của khách (VNĐ)")
    monthly_capacity_vnd: int = Field(..., ge=0, description="Khả năng tích lũy/chi trả hàng tháng (VNĐ)")
    objective: OptimizationObjective = Field(default=OptimizationObjective.MIN_INITIAL_CASH)
    policy_snapshot_hash: str | None = None
    active_policy_ids: list[str] = Field(default_factory=list)


class PricingResult(BaseModel):
    """Kết quả tính toán trả về từ Pricing Sidecar UDS."""
    schema_version: str = Field(default="pricing-result.v1")
    calculation_hash: str = Field(..., description="Băm SHA-256 kết quả tính toán tất định")
    scenarios: dict[str, ScenarioDetail] = Field(..., description="Từ điển 3 kịch bản tính toán")
    recommended_scenario_code: ScenarioCode = Field(..., description="Kịch bản được xếp hạng 1 tối ưu nhất")
    sanity_passed: bool = Field(..., description="Đạt trọn vẹn 6 Sanity Checks kế toán")
    sanity_errors: list[str] = Field(default_factory=list, description="Danh sách lỗi sanity nếu có")
