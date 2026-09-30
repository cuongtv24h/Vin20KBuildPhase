"""
Lead Dossier & Pre-Sales Session persistence service (C-10).
Owner: Phase 2 — Pre-Sales Advisory StateGraph

Ranh giới: chỉ ghi các bảng Pre-Sales (pre_sales_sessions, pre_sales_plans,
customer_consents, lead_dossiers). TUYỆT ĐỐI không ghi quotes, outbox, audit
trail hay gọi KMS (Zero-Trust Invariant #3).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.contracts.common import mask_phone
from src.contracts.dossier import LeadTemperature
from src.contracts.enums import LeadDossierStatus, PreSalesSessionStatus
from src.contracts.errors import DomainError, ErrorCode
from src.db.models import (
    CustomerConsentModel,
    LeadDossierModel,
    PreSalesPlanModel,
    PreSalesSessionModel,
)

SLA_MINUTES = 15  # SLA chuyên viên tiếp nhận lead
SESSION_TTL_SECONDS = 1800  # TTL phiên chat Pre-Sales (30 phút)


def utcnow() -> datetime:
    return datetime.now(UTC)


def classify_lead_temperature(own_funds_vnd: int, total_contract_price_vnd: int) -> LeadTemperature:
    """
    Phân loại nhiệt độ lead theo tỷ lệ vốn tự có / tổng giá trị hợp đồng:
    HOT >= 30%, WARM >= 15%, COLD < 15%.
    """
    if total_contract_price_vnd <= 0:
        return LeadTemperature.COLD
    ratio = own_funds_vnd / total_contract_price_vnd
    if ratio >= 0.30:
        return LeadTemperature.HOT
    if ratio >= 0.15:
        return LeadTemperature.WARM
    return LeadTemperature.COLD


class PreSalesDossierService:
    """Quản lý vòng đời phiên Pre-Sales → Plan → Consent → LeadDossier."""

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def create_session(
        self,
        db: AsyncSession,
        tenant_id: str = "DEFAULT",
        initial_message: str | None = None,
        session_id: str | None = None,
    ) -> PreSalesSessionModel:
        """Khởi tạo phiên Pre-Sales với TTL 1800s. `session_id` cho phép đồng bộ
        thread identity LangGraph (mặc định tự sinh PS-...)."""
        session = PreSalesSessionModel(
            session_id=session_id or f"PS-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}",
            tenant_id=tenant_id,
            status=PreSalesSessionStatus.ACTIVE.value,
            constraints_json={"initial_message": initial_message or ""},
            created_at=utcnow(),
            expires_at=utcnow() + timedelta(seconds=SESSION_TTL_SECONDS),
        )
        db.add(session)
        await db.flush()
        return session

    async def get_session(
        self, db: AsyncSession, session_id: str
    ) -> PreSalesSessionModel:
        session = (
            await db.execute(
                select(PreSalesSessionModel).where(
                    PreSalesSessionModel.session_id == session_id
                )
            )
        ).scalars().first()
        if session is None:
            raise DomainError(
                ErrorCode.NOT_FOUND,
                f"Pre-Sales session '{session_id}' không tồn tại.",
                details={"session_id": session_id},
            )
        return session

    async def expire_if_needed(self, db: AsyncSession, session_id: str) -> PreSalesSessionModel:
        """Tự động chuyển phiên EXPIRED nếu quá TTL 1800s."""
        session = await self.get_session(db, session_id)
        if (
            session.status == PreSalesSessionStatus.ACTIVE.value
            and session.expires_at.replace(tzinfo=UTC) < utcnow()
        ):
            session.status = PreSalesSessionStatus.EXPIRED.value
            await db.flush()
        return session

    # ------------------------------------------------------------------
    # Plan persistence (bản ước tính tham khảo — không phải báo giá)
    # ------------------------------------------------------------------

    async def save_plan(
        self,
        db: AsyncSession,
        session_id: str,
        unit_code: str,
        scenarios: dict[str, Any],
        recommended_code: str,
    ) -> PreSalesPlanModel:
        session = await self.get_session(db, session_id)
        plan = PreSalesPlanModel(
            plan_id=f"PLAN-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}",
            session_id=session.session_id,
            unit_code=unit_code,
            scenarios_json=scenarios,
            recommended_scenario_code=recommended_code,
            pdf_url=None,
            created_at=utcnow(),
        )
        db.add(plan)
        await db.flush()
        return plan

    async def set_plan_pdf_url(
        self, db: AsyncSession, plan_id: str, pdf_url: str
    ) -> PreSalesPlanModel:
        plan = (
            await db.execute(
                select(PreSalesPlanModel).where(PreSalesPlanModel.plan_id == plan_id)
            )
        ).scalars().first()
        if plan is None:
            raise DomainError(
                ErrorCode.NOT_FOUND,
                f"Plan '{plan_id}' không tồn tại.",
                details={"plan_id": plan_id},
            )
        plan.pdf_url = pdf_url
        await db.flush()
        return plan

    # ------------------------------------------------------------------
    # Consent & Dossier (F6 handoff, SLA 15 phút)
    # ------------------------------------------------------------------

    async def record_consent(
        self,
        db: AsyncSession,
        session_id: str,
        customer_name: str,
        customer_phone: str,
        customer_email: str | None = None,
        consent_scope: str = "PRE_SALES_ADVISORY_AND_SALES_CONTACT",
        ip_address: str | None = None,
    ) -> CustomerConsentModel:
        """Ghi nhận đồng thuận PII — bắt buộc trước khi tạo LeadDossier."""
        session = await self.get_session(db, session_id)
        consent = CustomerConsentModel(
            session_id=session.session_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            consent_scope=consent_scope,
            ip_address=ip_address,
            granted_at=utcnow(),
        )
        db.add(consent)
        await db.flush()
        return consent

    async def create_dossier(
        self,
        db: AsyncSession,
        session_id: str,
        customer_name: str,
        customer_phone: str,
        constraints: dict[str, Any] | None = None,
        plan_id: str | None = None,
        lead_temperature: LeadTemperature = LeadTemperature.WARM,
        assigned_sales_id: str | None = None,
    ) -> LeadDossierModel:
        """Tạo LeadDossier NEW với SLA 15 phút cho chuyên viên tiếp nhận."""
        session = await self.get_session(db, session_id)
        dossier = LeadDossierModel(
            dossier_id=f"LD-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}",
            session_id=session.session_id,
            status=LeadDossierStatus.NEW.value,
            lead_temperature=lead_temperature.value,
            customer_name=customer_name,
            customer_phone_masked=mask_phone(customer_phone),
            assigned_sales_id=assigned_sales_id,
            sla_expires_at=utcnow() + timedelta(minutes=SLA_MINUTES),
            quote_id=None,
            created_at=utcnow(),
        )
        db.add(dossier)

        # Chuyển phiên sang HANDED_OFF sau khi bàn giao
        session.status = PreSalesSessionStatus.HANDED_OFF.value
        if constraints is not None:
            session.constraints_json = constraints
        await db.flush()
        return dossier

    async def list_dossiers(
        self,
        db: AsyncSession,
        status: LeadDossierStatus | None = None,
        limit: int = 50,
    ) -> list[LeadDossierModel]:
        stmt = (
            select(LeadDossierModel)
            .options(selectinload(LeadDossierModel.session))
            .order_by(LeadDossierModel.sla_expires_at.asc())
        )
        if status is not None:
            stmt = stmt.where(LeadDossierModel.status == status.value)
        stmt = stmt.limit(limit)
        return list((await db.execute(stmt)).scalars().all())

    async def assign_sales(
        self, db: AsyncSession, dossier_id: str, sales_id: str
    ) -> LeadDossierModel:
        """Chuyên viên nhận lead: NEW → ASSIGNED, SLA countdown dừng ở đây."""
        dossier = (
            await db.execute(
                select(LeadDossierModel).where(LeadDossierModel.dossier_id == dossier_id)
            )
        ).scalars().first()
        if dossier is None:
            raise DomainError(
                ErrorCode.NOT_FOUND,
                f"Lead dossier '{dossier_id}' không tồn tại.",
                details={"dossier_id": dossier_id},
            )
        dossier.assigned_sales_id = sales_id
        dossier.status = LeadDossierStatus.ASSIGNED.value
        await db.flush()
        return dossier

    async def mark_converted(
        self, db: AsyncSession, dossier_id: str, quote_id: str
    ) -> LeadDossierModel:
        """Đánh dấu dossier đã chuyển đổi thành báo giá chính thức (C-10 → C-01)."""
        dossier = (
            await db.execute(
                select(LeadDossierModel).where(LeadDossierModel.dossier_id == dossier_id)
            )
        ).scalars().first()
        if dossier is None:
            raise DomainError(
                ErrorCode.NOT_FOUND,
                f"Lead dossier '{dossier_id}' không tồn tại.",
                details={"dossier_id": dossier_id},
            )
        dossier.status = LeadDossierStatus.CONVERTED_TO_QUOTE.value
        dossier.quote_id = quote_id
        await db.flush()
        return dossier
