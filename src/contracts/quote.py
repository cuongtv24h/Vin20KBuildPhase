"""
Official Quote contracts (C-01, C-05).
"""

from datetime import datetime

from pydantic import BaseModel, Field

from src.contracts.common import TransactionContext
from src.contracts.enums import ApprovalStatus, OptimizationObjective, PdfStatus, QuoteWorkflowStatus
from src.contracts.pricing import PricingResult, ScenarioDetail


class QuoteCreateRequest(BaseModel):
    """Yêu cầu khởi tạo Báo giá chính thức mới từ giao diện Sales."""
    project_id: str = Field(..., description="Mã dự án (vd: BEVERLY)")
    unit_code: str = Field(..., description="Mã căn hộ (vd: BEV-12.04)")
    transaction_date: str = Field(..., description="Ngày giao dịch hợp đồng (YYYY-MM-DD)")
    customer_name: str = Field(..., min_length=2, description="Tên khách hàng đầy đủ")
    customer_phone: str = Field(..., min_length=9, description="Số điện thoại khách hàng")
    customer_id_card: str | None = Field(None, description="Số CCCD/CMND khách hàng")
    customer_segment: str = Field(default="STANDARD")
    channel: str = Field(default="DIRECT")
    objective: OptimizationObjective = Field(default=OptimizationObjective.MIN_INITIAL_CASH)
    dossier_id: str | None = Field(None, description="Mã lead dossier nếu chuyển đổi từ phễu Pre-Sales")


class QuoteSnapshot(BaseModel):
    """Bản ghi snapshot trạng thái nghiệp vụ và tài chính bất biến của Báo giá."""
    quote_id: str
    quote_version: int
    context: TransactionContext
    pricing_result: PricingResult
    policy_snapshot_hash: str
    status: QuoteWorkflowStatus
    created_at: datetime
    created_by: str


class ApprovalPackage(BaseModel):
    """Hồ sơ gói phê duyệt trình Quản lý thẩm định (HITL Gate)."""
    quote_id: str
    quote_version: int
    snapshot_hash: str
    recommended_scenario: ScenarioDetail
    risk_flags: list[str] = Field(default_factory=list, description="Danh sách cờ cảnh báo rủi ro Đỏ/Vàng")
    sod_check_passed: bool = Field(..., description="Đạt chuẩn phân quyền độc lập Separation of Duties")
    evidence_count: int = Field(default=0, description="Số lượng mỏ neo dẫn chứng pháp lý F4 đã xác thực")


class HumanReviewDecision(BaseModel):
    """Phán quyết phê duyệt hoặc yêu cầu sửa đổi của Quản lý."""
    approved: bool
    rejection_reason: str | None = None
    revision_instructions: str | None = None


class OfficialQuoteResponse(BaseModel):
    """Thông tin phản hồi đầy đủ của một Báo giá chính thức."""
    quote_id: str
    quote_version: int
    status: QuoteWorkflowStatus
    approval_status: ApprovalStatus
    pdf_status: PdfStatus
    snapshot: QuoteSnapshot | None = None
    signature: str | None = Field(None, description="Chữ ký số Ed25519 từ KMS nếu đã phê duyệt")
    snapshot_hash: str | None = None
    qr_code_url: str | None = None
    pdf_url: str | None = None
    etag: str = Field(..., description="Mã ETag phiên bản phục vụ khóa lạc quan OCC")
