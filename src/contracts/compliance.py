"""
Sales Message Compliance Gate contracts (C-11, F8).
"""


from pydantic import BaseModel, Field

from src.contracts.common import SourceCoordinate
from src.contracts.enums import ComplianceCheckTrigger, ComplianceStatus, ComplianceTier


class ComplianceCheckRequest(BaseModel):
    """Yêu cầu thẩm định tuân thủ thông điệp bán hàng (F8)."""
    message_text: str = Field(..., min_length=1, description="Nội dung tin nhắn Sale soạn gửi khách")
    quote_id: str | None = Field(None, description="Mã báo giá chính thức liên kết nếu có")
    plan_id: str | None = Field(None, description="Mã phương án tham khảo liên kết nếu có")
    channel: str = Field(default="ZALO", description="Kênh gửi tin: ZALO, SMS, EMAIL")
    trigger: ComplianceCheckTrigger = Field(default=ComplianceCheckTrigger.ON_DEBOUNCE)


class ClaimVerificationItem(BaseModel):
    """Kết quả thẩm định 1 khẳng định tài chính trong tin nhắn."""
    claim_text: str = Field(..., description="Đoạn câu chứa khẳng định số liệu hoặc cam kết")
    claim_type: str = Field(..., description="PRICE, DISCOUNT, INTEREST_RATE, GRACE_PERIOD, GIFT, COMMITMENT")
    status: ComplianceStatus
    evidence_refs: list[SourceCoordinate] = Field(default_factory=list)
    detected_amount_vnd: int | None = None
    explanation: str


class ComplianceCheckResponse(BaseModel):
    """Kết quả thẩm định tuân thủ thông điệp toàn diện."""
    check_id: str
    message_hash: str = Field(..., description="Băm SHA-256 nội dung tin nhắn phục vụ khóa cổng gửi")
    overall_status: ComplianceStatus
    compliance_tier: ComplianceTier
    claims: list[ClaimVerificationItem] = Field(default_factory=list)
    can_send: bool = Field(..., description="Cờ cho phép gửi tin nhắn")
    can_copy: bool = Field(..., description="Cờ cho phép sao chép tin nhắn vào clipboard")
    rejection_reasons: list[str] = Field(default_factory=list)
    suggested_rewrite: str | None = Field(None, description="Gợi ý câu chữ sửa đổi đạt chuẩn")


class SendMessageCommand(BaseModel):
    """Lệnh gửi tin nhắn chính thức qua cổng Backend-Enforced Gate."""
    message_hash: str = Field(..., description="Bắt buộc truyền hash đã được thẩm định hợp lệ")
    recipient_phone: str
    message_text: str
    channel: str = Field(default="ZALO")
