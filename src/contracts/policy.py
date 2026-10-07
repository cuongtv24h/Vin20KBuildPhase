"""
Policy Registry, Ingestion & F9 Structured Rule contracts (C-02, C-03).
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from src.contracts.enums import PolicyRuleStatus


class PolicyDocumentDTO(BaseModel):
    """Thông tin văn bản chính sách bán hàng."""
    document_id: str = Field(..., description="Mã tài liệu (vd: DOC-POL-04)")
    title: str = Field(..., description="Tiêu đề chính sách")
    document_hash: str = Field(..., description="Băm SHA-256 toàn bộ nội dung file gốc")
    effective_from: date = Field(..., description="Ngày bắt đầu hiệu lực")
    effective_to: date = Field(..., description="Ngày kết thúc hiệu lực")
    status: str = Field(default="ACTIVE", description="ACTIVE, EXPIRED, SUPERSEDED")
    version: str = Field(default="v1.0")


class PolicyChunkDTO(BaseModel):
    """Mẫu chunk văn bản chính sách phục vụ tìm kiếm ngữ nghĩa pgvector."""
    chunk_id: str
    document_id: str
    section: str | None = None
    clause_id: str
    content: str
    page: int
    chunk_hash: str
    embedding: list[float] | None = Field(None, description="Vector embedding 384 chiều")


class StructuredRuleDTO(BaseModel):
    """Quy tắc chính sách có cấu trúc trích xuất bởi phân hệ F9."""
    rule_id: str
    policy_id: str
    policy_version: str
    clause_id: str
    rule_type: str = Field(..., description="DISCOUNT, PAYMENT_PROGRESS, LOAN_SUBSIDY, GIFT")
    condition_json: dict[str, Any] = Field(..., description="Biểu thức điều kiện dạng JSON Logic")
    benefit_formula: dict[str, Any] = Field(..., description="Công thức tính toán giá trị ưu đãi")
    priority: int = Field(default=10, description="Độ ưu tiên áp dụng (số nhỏ ưu tiên trước)")
    status: PolicyRuleStatus = Field(default=PolicyRuleStatus.DRAFT)
    regression_test_pass_rate: float = Field(default=0.0, description="Tỷ lệ pass test suite hồi quy (0.0 đến 1.0)")


class RulePublishRequest(BaseModel):
    """Yêu cầu phát hành quy tắc chính sách lên môi trường ACTIVE."""
    rule_id: str
    enforce_test_gate: bool = Field(default=True, description="Bắt buộc test pass 100% mới cho phép publish")


class RulePublishResponse(BaseModel):
    """Kết quả phát hành quy tắc chính sách F9."""
    rule_id: str
    status: PolicyRuleStatus
    regression_pass_rate: float
    published_at: datetime | None = None
    message: str
