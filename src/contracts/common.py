"""
Common domain models and cryptographic utilities for PricePolicy AI Agent.
"""

import hashlib
import json
from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from src.contracts.enums import PolicyDecisionStatus


class SourceCoordinate(BaseModel):
    """
    Tọa độ mỏ neo vật lý của dẫn chứng pháp lý trong tài liệu chính sách (F4).
    """
    document_id: str = Field(..., description="Mã định danh tài liệu chính sách (vd: DOC-POL-04)")
    document_version: str = Field(..., description="Phiên bản tài liệu (vd: v3.1)")
    document_hash: str = Field(..., description="Băm SHA-256 của toàn bộ tài liệu nguồn")
    page: int = Field(..., ge=1, description="Số trang chứa điều khoản dẫn chứng")
    section: str | None = Field(None, description="Mục/Phần (vd: Mục 4.2)")
    clause_id: str = Field(..., description="Mã điều khoản (vd: CLAUSE-4.2.1)")
    verbatim_text: str | None = Field(None, description="Trích đoạn nguyên văn điều khoản")


class TransactionContext(BaseModel):
    """
    Ngữ cảnh giao dịch đầu vào để thẩm định chính sách Time-Travel và tính giá.
    """
    tenant_id: str = Field(default="DEFAULT", description="Mã đối tác / tenant")
    project_id: str = Field(..., description="Mã dự án bất động sản (vd: BEVERLY)")
    unit_code: str = Field(..., description="Mã căn hộ (vd: BEV-12.04)")
    listed_price_before_tax_vnd: int = Field(..., gt=0, description="Giá niêm yết chưa thuế (VNĐ)")
    transaction_date: date = Field(..., description="Ngày giao dịch hợp đồng thực tế")
    customer_segment: str = Field(default="STANDARD", description="Phân khúc khách hàng: STANDARD, VIP, LOYAL")
    channel: str = Field(default="DIRECT", description="Kênh bán hàng: DIRECT, AGENCY")
    is_staff: bool = Field(default=False, description="Khách hàng là cán bộ nhân viên")


class PolicyClauseEvaluation(BaseModel):
    """
    Kết quả thẩm định điều khoản chính sách tại node N-06.
    """
    clause_id: str = Field(..., description="Mã điều khoản")
    policy_id: str = Field(..., description="Mã chính sách")
    policy_version: str = Field(..., description="Phiên bản chính sách")
    status: PolicyDecisionStatus = Field(..., description="Trạng thái hợp lệ điều khoản")
    evidence_quote: str = Field(..., description="Trích dẫn chứng cứ")
    chunk_hash: str = Field(..., description="Băm SHA-256 của chunk văn bản")
    source_coordinates: list[SourceCoordinate] = Field(default_factory=list)


def canonical_json_bytes(payload: Any) -> bytes:
    """
    Chuẩn hóa JSON canonical (RFC 8785):
    - Khóa từ điển được sắp xếp theo thứ tự từ điển (sort_keys=True)
    - Không có khoảng trắng dư thừa (separators=(',', ':'))
    - Giữ nguyên UTF-8 không escape ký tự tiếng Việt (ensure_ascii=False)
    """
    if isinstance(payload, BaseModel):
        data = payload.model_dump(mode="json")
    else:
        data = payload
    json_str = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return json_str.encode("utf-8")


def sha256_hex(data: bytes | str) -> str:
    """Tính chuỗi băm SHA-256 dạng hex."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()
