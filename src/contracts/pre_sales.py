"""
Pre-Sales Advisory contracts (C-09).
"""

from datetime import datetime

from pydantic import BaseModel, Field

from src.contracts.enums import OptimizationObjective, PreSalesSessionStatus
from src.contracts.pricing import ScenarioCode, ScenarioDetail


class CustomerConstraints(BaseModel):
    """Bộ ràng buộc tài chính và nhu cầu của khách hàng được trích xuất."""
    own_funds_vnd: int = Field(default=0, ge=0, description="Vốn tự có ban đầu (VNĐ)")
    monthly_capacity_vnd: int = Field(default=0, ge=0, description="Thu nhập/khả năng trả nợ hàng tháng (VNĐ)")
    project_id: str | None = Field(None, description="Dự án quan tâm")
    unit_type: str | None = Field(None, description="Loại căn: STUDIO, 1BR, 2BR, 3BR")
    preferred_unit_code: str | None = Field(None, description="Mã căn cụ thể nếu có")
    objective: OptimizationObjective = Field(default=OptimizationObjective.MIN_INITIAL_CASH)
    urgency_months: int | None = Field(None, description="Thời gian dự kiến vào ở hoặc nhận nhà (tháng)")


class PreSalesSessionCreateRequest(BaseModel):
    """Yêu cầu khởi tạo phiên tư vấn Pre-Sales mới."""
    initial_message: str | None = Field(None, description="Lời nhắn mở đầu của khách")
    project_id: str | None = Field(None, description="Dự án quan tâm ban đầu")


class PreSalesSessionResponse(BaseModel):
    """Thông tin phiên tư vấn Pre-Sales."""
    session_id: str
    tenant_id: str = "DEFAULT"
    status: PreSalesSessionStatus
    created_at: datetime
    expires_at: datetime
    constraints: CustomerConstraints | None = None
    plan_id: str | None = None
    last_agent_message: str | None = None


class ConstraintConfirmationRequest(BaseModel):
    """Xác nhận hoặc điều chỉnh các ràng buộc ngân sách."""
    confirmed: bool = Field(..., description="Khách hàng xác nhận đúng nhu cầu")
    revised_constraints: CustomerConstraints | None = None


class PreSalesPlanResponse(BaseModel):
    """Bản ước tính phương án tài chính tham khảo (Pre-Sales Reference Plan)."""
    plan_id: str
    session_id: str
    unit_code: str
    listed_price_before_tax_vnd: int
    scenarios: dict[str, ScenarioDetail]
    recommended_scenario_code: ScenarioCode
    watermark_text: str = Field(
        default="BẢN ƯỚC TÍNH THAM KHẢO TIỀN BÁN HÀNG - KHÔNG PHẢI BÁO GIÁ CHÍNH THỨC",
        description="Watermark bắt buộc trên toàn bộ tài liệu tham khảo Pre-Sales"
    )
    disclaimer: str = Field(
        default="Phương án chỉ mang tính chất tham khảo, không cấu thành cam kết báo giá chính thức của chủ đầu tư.",
        description="Tuyên bố từ chối trách nhiệm pháp lý"
    )
    pdf_download_url: str


class HandoffConsentRequest(BaseModel):
    """Xác nhận đồng thuận chia sẻ thông tin cá nhân và kết nối chuyên viên bán hàng (F6)."""
    consent_granted: bool = Field(..., description="Đồng ý chia sẻ dữ liệu")
    customer_name: str = Field(..., min_length=2, description="Họ và tên khách hàng")
    customer_phone: str = Field(..., min_length=9, description="Số điện thoại liên hệ")
    customer_email: str | None = None
    privacy_terms_acknowledged: bool = Field(..., description="Đã đọc và đồng ý điều khoản bảo mật PII")
