"""
Sales Message Compliance Gate (C-11, F8) — tầng service.
Enforces speech guidelines (POL-08) and validates claim evidence across 3 checkpoints:
- ON_DRAFT: Real-time typing suggestions
- DEBOUNCE: Form level pre-check
- FINAL_SEND: Hard enforcement gate (blocks prohibited or unverified messages)
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.contracts.common import sha256_hex
from src.contracts.enums import ComplianceStatus, ComplianceTier
from src.contracts.errors import DomainError, ErrorCode
from src.db.models import ComplianceCheckModel
from src.services.compliance.rules import POL_08_PROHIBITED_PATTERNS


class ComplianceCheckRequest(BaseModel):
    """Request schema for compliance checking."""

    message: str = Field(..., description="Message text to inspect")
    mode: str = Field("FINAL_SEND", description="ON_DRAFT, DEBOUNCE, or FINAL_SEND")
    quote_id: str | None = Field(None, description="Associated quote ID")
    quote_version: int | None = Field(None, description="Associated quote version")
    policy_version_refs: list[str] = Field(default_factory=list, description="Referenced policy versions")
    claimed_evidence_ids: list[str] = Field(default_factory=list, description="IDs of linked evidence items")


class ComplianceClaimFinding(BaseModel):
    """Specific finding on a claim inside the message."""

    claim_text: str
    tier: str = Field(..., description="SUPPORTED, CONDITIONAL, UNSUPPORTED, PROHIBITED")
    rule_id: str | None = None
    reason: str


class ComplianceCheckResponse(BaseModel):
    """Response schema matching Section 10.4 compliance contract."""

    check_id: str
    message_hash: str
    mode: str
    overall_status: str = Field(..., description="SUPPORTED, CONDITIONAL, UNSUPPORTED, PROHIBITED")
    quote_id: str | None = None
    quote_version: int | None = None
    policy_version_refs: list[str] = Field(default_factory=list)
    claims: list[ComplianceClaimFinding] = Field(default_factory=list)
    required_action: str = Field(..., description="ALLOW_SEND, WARN_CONDITIONAL, BLOCK_MESSAGE_COMPLIANCE_VIOLATION")


class ComplianceGate:
    """Core Compliance Gate Engine (C-11)."""

    def check(self, request: ComplianceCheckRequest) -> ComplianceCheckResponse:
        """Inspect a message and determine compliance status according to mode."""
        msg = request.message
        findings: list[ComplianceClaimFinding] = []

        # 1. Quét vi phạm cấm tuyệt đối theo POL-08
        has_prohibited = False
        for pattern in POL_08_PROHIBITED_PATTERNS:
            match = re.search(pattern.regex, msg, re.IGNORECASE)
            if match:
                has_prohibited = True
                findings.append(
                    ComplianceClaimFinding(
                        claim_text=match.group(0),
                        tier="PROHIBITED",
                        rule_id=pattern.pattern_id,
                        reason=pattern.description,
                    )
                )

        # 2. Phân tích các claim định lượng tài chính
        financial_discount_match = re.search(r"chiết khấu\s+\d+(\.\d+)?%", msg, re.IGNORECASE)
        if financial_discount_match:
            claim_str = financial_discount_match.group(0)
            if not request.policy_version_refs and not request.claimed_evidence_ids:
                if request.mode == "FINAL_SEND":
                    tier = "UNSUPPORTED"
                    reason = "Phát ngôn chiết khấu tài chính nhưng không có mỏ neo chứng từ chính sách (EvidenceBundle)."
                else:
                    tier = "CONDITIONAL"
                    reason = "Cần đính kèm chứng từ chính sách hợp lệ trước khi gửi chính thức."
                findings.append(
                    ComplianceClaimFinding(
                        claim_text=claim_str,
                        tier=tier,
                        rule_id="RULE-EVIDENCE-REQUIRED",
                        reason=reason,
                    )
                )
            else:
                findings.append(
                    ComplianceClaimFinding(
                        claim_text=claim_str,
                        tier="SUPPORTED",
                        rule_id="RULE-EVIDENCE-LINKED",
                        reason="Đã liên kết mỏ neo chứng cứ chính sách hợp lệ.",
                    )
                )

        # 3. Tổng hợp trạng thái
        if has_prohibited:
            overall_status = "PROHIBITED"
            action = "BLOCK_MESSAGE_COMPLIANCE_VIOLATION"
        elif any(f.tier == "UNSUPPORTED" for f in findings):
            overall_status = "UNSUPPORTED"
            action = "BLOCK_MESSAGE_COMPLIANCE_VIOLATION" if request.mode == "FINAL_SEND" else "WARN_UNSUPPORTED"
        elif any(f.tier == "CONDITIONAL" for f in findings):
            overall_status = "CONDITIONAL"
            action = "SUGGEST_LINKING_EVIDENCE" if request.mode == "ON_DRAFT" else "WARN_CONDITIONAL"
        else:
            overall_status = "SUPPORTED"
            action = "ALLOW_SEND"

        msg_hash = hashlib.sha256(msg.encode("utf-8")).hexdigest()
        check_id = f"CHK-{uuid.uuid4().hex[:8].upper()}"

        return ComplianceCheckResponse(
            check_id=check_id,
            message_hash=msg_hash,
            mode=request.mode,
            overall_status=overall_status,
            quote_id=request.quote_id,
            quote_version=request.quote_version,
            policy_version_refs=request.policy_version_refs,
            claims=findings,
            required_action=action,
        )


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
    - Cam kết cấm (sinh lời/hoàn vốn) -> PROHIBITED.
    - Claim số tài chính không kèm mã điều khoản [POL-...] -> UNSUPPORTED.
    - Claim có dẫn chứng (mã điều khoản) -> SUPPORTED.
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
        Cổng gửi tin duy nhất của Backend (F8).
        """
        cleaned_phone = validate_phone_format(recipient_phone)

        text_hash = sha256_hex(message_text)
        if text_hash != message_hash:
            raise DomainError(
                ErrorCode.COMPLIANCE_SEND_BLOCKED,
                "Nội dung tin nhắn không khớp hash đã thẩm định (anti-tamper).",
                http_status=403,
            )

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
                f"Chặn gửi: trạng thái tuân thủ {record.overall_status} (tier {record.compliance_tier}).",
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
