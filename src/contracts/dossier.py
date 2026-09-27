"""
Sales Lead Dossier & Handover contracts (C-10).
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from src.contracts.enums import LeadDossierStatus
from src.contracts.pre_sales import CustomerConstraints


class LeadTemperature(StrEnum):
    """Nhiệt độ sẵn sàng giao dịch của Lead."""
    HOT = "HOT"      # Vốn tự có >= 30% giá trị căn hộ
    WARM = "WARM"    # Vốn tự có >= 15%
    COLD = "COLD"    # Vốn tự có < 15% hoặc chưa rõ nhu cầu


class LeadDossierResponse(BaseModel):
    """Hồ sơ bàn giao khách hàng tiềm năng cho Sales Dashboard."""
    dossier_id: str
    session_id: str
    status: LeadDossierStatus
    lead_temperature: LeadTemperature
    customer_name: str
    customer_phone_masked: str = Field(..., description="Số điện thoại che dấu bảo mật (vd: 09***1234)")
    customer_email_masked: str | None = None
    constraints: CustomerConstraints
    plan_id: str | None = None
    assigned_sales_id: str | None = None
    created_at: datetime
    sla_expires_at: datetime = Field(..., description="Thời hạn SLA 15 phút tiếp nhận lead")
    quote_id: str | None = Field(None, description="Mã báo giá chính thức nếu đã chuyển đổi")


class CreateQuoteFromDossierRequest(BaseModel):
    """Yêu cầu tạo Báo giá chính thức (Official Quote v1) từ Lead Dossier."""
    dossier_id: str = Field(..., description="Mã hồ sơ khách hàng bàn giao")
    unit_code: str | None = Field(None, description="Mã căn hộ chốt chính thức (nếu đổi so với tham khảo)")
    override_transaction_date: str | None = Field(None, description="Ngày giao dịch chính thức (YYYY-MM-DD)")
