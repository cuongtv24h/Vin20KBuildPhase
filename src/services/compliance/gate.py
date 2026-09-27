"""
Sales Message Compliance Gate (C-11, F8) — tầng service.
Owner: Phase 5 — phục vụ E2E chặng 5 (F8 Send Gate). File MỚI, ngoài phạm vi Phase 4.

Ranh giới: chỉ ghi bảng `compliance_checks` (DDL Phase 0). KHÔNG đụng router/deps
của Phase 4; endpoint POST /messages/send của Phase 4 sẽ gọi thẳng vào module này.

Invariants:
- F8: tin nhắn có claim tài chính không có dẫn chứng phải bị UNSUPPORTED/PROHIBITED → cấm gửi.
- Chỉ Backend mới được thực thi gửi tin (client không được bypass).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.contracts.common import sha256_hex
from src.contracts.enums import ComplianceStatus, ComplianceTier
from src.contracts.errors import DomainError, ErrorCode
from src.db.models import ComplianceCheckModel

# Claim tài chính: số tiền VNĐ, phần trăm chiết khấu, lãi suất, ân hạn
# (cho phép từ đệm giữa từ khóa và con số: 'lãi suất ưu đãi 12%', 'giảm ngay 20%')
CLAIM_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("PRICE", re.compile(r"(\d+(?:[.,]\d+)*)\s*(tỷ|triệu|vnđ|vnd|đồng)", re.IGNORECASE)),
    ("DISCOUNT", re.compile(r"(chiết khấu|giảm|khuyến mãi)[^\d%]{0,20}(\d+(?:[.,]\d+)*)\s*%", re.IGNORECASE)),
    ("INTEREST_RATE", re.compile(r"lãi suất[^\d%]{0,20}(\d+(?:[.,]\d+)*)\s*%", re.IGNORECASE)),
    ("GRACE_PERIOD", re.compile(r"ân hạn[^\d%]{0,20}(\d+)\s*tháng", re.IGNORECASE)),
    ("COMMITMENT", re.compile(r"(cam kết|đảm bảo|chắc chắn)\s+(giá|lãi|sinh lời|bán được)", re.IGNORECASE)),
]

PROHIBITED_COMMITMENTS = re.compile(
    r"(cam kết|đảm bảo|chắc chắn)\s+(sinh lời|bán lại|lãi|hoàn vốn|lợi nhuận|có lãi)", re.IGNORECASE
)


def analyze_message_claims(message_text: str) -> list[dict[str, Any]]:
    """
    Phân rã tin nhắn thành các claim tiềm năng với trạng thái tuân thủ:
    - Cam kết cấm (sinh lời/hoàn vốn) → PROHIBITED.
    - Claim số tài chính không kèm mã điều khoản [POL-...] → UNSUPPORTED.
    - Claim có dẫn chứng (mã điều khoản) → SUPPORTED.
    """
    claims: list[dict[str, Any]] = []
    prohibited_match = PROHIBITED_COMMITMENTS.search(message_text)
    if prohibited_match:
        claims.append(
            {
                "claim_text": prohibited_match.group(0),
                "claim_type": "COMMITMENT",
                "status": ComplianceStatus.PROHIBITED.value,
                "evidence_refs": [],
                "explanation": "Cam kết sinh lời/hoàn vốn bị cấm tuyệt đối theo F8.",
            }
        )

    for claim_type, pattern in CLAIM_PATTERNS:
        match = pattern.search(message_text)
        if not match:
            continue
        has_evidence = bool(re.search(r"\[POL-[A-Z0-9\-]+\]", message_text))
        if claim_type == "COMMITMENT":
            status = ComplianceStatus.SUPPORTED if has_evidence else ComplianceStatus.UNSUPPORTED
        elif has_evidence:
            status = ComplianceStatus.SUPPORTED
        else:
            status = ComplianceStatus.UNSUPPORTED
        claims.append(
            {
                "claim_text": match.group(0),
                "claim_type": claim_type,
                "status": status.value,
                "evidence_refs": ["[POL-...]"] if has_evidence else [],
                "explanation": (
                    "Claim có mỏ neo tọa độ điều khoản."
                    if has_evidence
                    else "Claim tài chính thiếu dẫn chứng SourceCoordinate/điều khoản."
                ),
            }
        )
    return claims


def determine_tier(claims: list[dict[str, Any]]) -> ComplianceTier:
    """Phân hạng rủi ro: BLACK > RED > YELLOW > GREEN theo claim xấu nhất."""
    statuses = {c["status"] for c in claims}
    if ComplianceStatus.PROHIBITED.value in statuses:
        return ComplianceTier.TIER_4_BLACK
    if ComplianceStatus.UNSUPPORTED.value in statuses:
        return ComplianceTier.TIER_3_RED
    if ComplianceStatus.CONDITIONAL.value in statuses:
        return ComplianceTier.TIER_2_YELLOW
    return ComplianceTier.TIER_1_GREEN

PHONE_PATTERN = re.compile(r"^0\d{9,10}$")


def validate_phone_format(phone: str) -> str:
    """Validate Vietnamese phone number format and return cleaned digits."""
    cleaned = re.sub(r"[\s\-\.\(\)]+", "", (phone or "").strip())
    if not PHONE_PATTERN.match(cleaned):
        raise DomainError(
            ErrorCode.INPUT_VALIDATION_ERROR,
            "Số điện thoại không hợp lệ (yêu cầu 10-11 chữ số, bắt đầu bằng 0).",
            http_status=400,
            details={"field": "recipient_phone"},
        )
    return cleaned


def mask_phone(phone: str) -> str:
    """Che số điện thoại bảo mật: giữ 2 số đầu + 4 số cuối."""
    phone = (phone or "").strip()
    if len(phone) >= 6:
        return phone[:2] + "*" * (len(phone) - 6) + phone[-4:]
    return "*" * len(phone)


class ComplianceGateService:
    """Service F8: thẩm định tin nhắn và thực thi cổng gửi duy nhất của Backend."""

    async def check_message(
        self,
        db: AsyncSession,
        message_text: str,
        quote_id: str | None = None,
        plan_id: str | None = None,
        channel: str = "ZALO",
    ) -> ComplianceCheckModel:
        """
        Thẩm định tin nhắn bán hàng, ghi bản ghi compliance_checks và trả về
        model record (can_send/can_copy/rejection_reasons suy ra từ record khi cần).
        """
        claims = analyze_message_claims(message_text)
        tier = determine_tier(claims)

        overall = ComplianceStatus.SUPPORTED
        if tier == ComplianceTier.TIER_4_BLACK:
            overall = ComplianceStatus.PROHIBITED
        elif tier == ComplianceTier.TIER_3_RED:
            overall = ComplianceStatus.UNSUPPORTED
        elif tier == ComplianceTier.TIER_2_YELLOW:
            overall = ComplianceStatus.CONDITIONAL

        can_send = tier in (ComplianceTier.TIER_1_GREEN, ComplianceTier.TIER_2_YELLOW)

        record = ComplianceCheckModel(
            check_id=f"CHK-{uuid4().hex[:12].upper()}",
            quote_id=quote_id,
            plan_id=plan_id,
            message_hash=sha256_hex(message_text),
            overall_status=overall.value,
            compliance_tier=tier.value,
            claims_json=claims,
            can_send=can_send,
        )
        db.add(record)
        await db.flush()
        return record

    async def enforce_send(
        self,
        db: AsyncSession,
        message_hash: str,
        message_text: str,
        recipient_phone: str,
        channel: str = "ZALO",
        quote_id: str | None = None,
        plan_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Cổng gửi tin duy nhất của Backend (F8). Chỉ cho phép gửi khi:
        - Có bản ghi compliance_checks với message_hash khớp.
        - Khớp đúng quote_id / plan_id nếu được chỉ định (chống mượn hash).
        - Trạng thái KHÔNG phải UNSUPPORTED/PROHIBITED.
        - Nội dung gửi băm ra khớp đúng message_hash đã thẩm định.
        Nếu vi phạm → DomainError COMPLIANCE_SEND_BLOCKED (HTTP 403 ở tầng API).
        """
        # Validate phone format trước khi xử lý
        cleaned_phone = validate_phone_format(recipient_phone)

        text_hash = sha256_hex(message_text)
        if text_hash != message_hash:
            raise DomainError(
                ErrorCode.COMPLIANCE_SEND_BLOCKED,
                "Nội dung tin nhắn không khớp hash đã thẩm định (anti-tamper).",
                http_status=403,
            )

        # Lấy bản ghi kiểm duyệt mới nhất khớp hash và quote_id/plan_id nếu có
        from sqlalchemy import select

        conditions = [ComplianceCheckModel.message_hash == message_hash]
        if quote_id:
            conditions.append(ComplianceCheckModel.quote_id == quote_id)
        if plan_id:
            conditions.append(ComplianceCheckModel.plan_id == plan_id)

        stmt = (
            select(ComplianceCheckModel)
            .where(*conditions)
            .order_by(ComplianceCheckModel.created_at.desc())
            .limit(1)
        )
        record = (await db.execute(stmt)).scalars().first()
        if record is None:
            raise DomainError(
                ErrorCode.COMPLIANCE_SEND_BLOCKED,
                "Tin nhắn chưa được thẩm định tuân thủ F8 (hoặc không khớp quote/plan chỉ định).",
                http_status=403,
            )

        if record.quote_id and quote_id and record.quote_id != quote_id:
            raise DomainError(
                ErrorCode.COMPLIANCE_SEND_BLOCKED,
                f"Tin nhắn được thẩm định cho quote '{record.quote_id}', không khớp với quote '{quote_id}'.",
                http_status=403,
            )

        if record.overall_status in (
            ComplianceStatus.UNSUPPORTED.value,
            ComplianceStatus.PROHIBITED.value,
        ):
            rejection_reasons = [
                c.get("explanation", "")
                for c in (record.claims_json or [])
                if c.get("status")
                in (ComplianceStatus.UNSUPPORTED.value, ComplianceStatus.PROHIBITED.value)
            ]
            raise DomainError(
                ErrorCode.COMPLIANCE_SEND_BLOCKED,
                f"Chặn gửi: trạng thái tuân thủ {record.overall_status} "
                f"(tier {record.compliance_tier}).",
                http_status=403,
                details={"check_id": record.check_id, "rejection_reasons": rejection_reasons},
            )

        return {
            "sent": True,
            "check_id": record.check_id,
            "recipient_phone": mask_phone(cleaned_phone),
            "channel": channel,
            "sent_at": datetime.now(UTC).isoformat(),
        }
