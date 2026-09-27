"""
Pre-Sales advisory nodes: PS-10 (Await Consent interrupt) và PS-11 (Safe Abstain / Handoff).
Owner: Phase 2 — Pre-Sales Advisory StateGraph (C-09)

Ranh giới: Handoff chỉ tạo LeadDossier + CustomerConsent (F6). Không sinh chữ ký số,
không chuyển trạng thái APPROVED, không ghi transactional_outbox (Invariant #3).
"""

from __future__ import annotations

from typing import Any

from src.agents.pre_sales.state import PreSalesState
from src.contracts.errors import DomainError, ErrorCode
from src.contracts.pre_sales import HandoffConsentRequest


def node_await_handoff_consent(state: PreSalesState) -> dict[str, Any]:
    """
    PS-10 — Await Consent (HITL interrupt): chờ khách đồng ý chia sẻ thông tin cá nhân.
    Consent PHẢI có: consent_granted=True + privacy_terms_acknowledged=True + đủ tên/SĐT.
    Nếu từ chối → đi nhánh Safe Abstain (PS-11).
    """
    consent = state.get("handoff_consent")

    if not consent:
        return {
            "status": "WAITING_FOR_HANDOFF_CONSENT",
            "_interrupt_gate": "WAITING_FOR_HANDOFF_CONSENT",
            "agent_message": (
                "Anh/chị có muốn em kết nối với chuyên viên bán hàng để nhận tư vấn chi tiết "
                "và giữ ưu đãi hiện hành không ạ? (Cần đồng ý chia sẻ họ tên và số điện thoại)"
            ),
        }

    try:
        parsed = HandoffConsentRequest(**consent)
    except Exception as exc:
        raise DomainError(
            ErrorCode.INPUT_VALIDATION_ERROR,
            "Dữ liệu đồng thuận handoff không hợp lệ.",
            details={"errors": str(exc)},
        ) from exc

    if not parsed.consent_granted or not parsed.privacy_terms_acknowledged:
        return {
            "handoff_consent": parsed.model_dump(mode="json"),
            "abstain_reason": "CONSENT_DECLINED",
            "status": "ABANDONED",
            "decision": "ABSTAIN",
            "_interrupt_gate": None,
        }

    return {
        "handoff_consent": parsed.model_dump(mode="json"),
        "status": "HANDED_OFF",
        "_interrupt_gate": None,
    }


def node_safe_abstain_or_handoff(state: PreSalesState) -> dict[str, Any]:
    """
    PS-11 — Safe Abstain / Handoff (pure node, không đụng DB):
    - Trả về quyết định HANDOFF_CREATE_DOSSIER kèm dữ liệu consent để tầng
      graph helper/API tạo LeadDossier + CustomerConsent (SLA 15 phút).
    - Nếu ABSTAINED/CONSENT_DECLINED → kết thúc an toàn, không thu thập PII.
    """
    status = state.get("status", "")
    if status in ("ABSTAINED", "ABANDONED") or state.get("abstain_reason"):
        reason = state.get("abstain_reason") or "SESSION_ENDED_WITHOUT_CONSENT"
        final_status = "ABANDONED" if reason == "CONSENT_DECLINED" else "ABSTAINED"
        return {
            "status": final_status,
            "decision": "ABSTAIN",
            "abstain_reason": reason,
            "agent_message": (
                "Cảm ơn anh/chị đã trò chuyện. Toàn bộ nội dung chỉ mang tính tham khảo, "
                "không cấu thành báo giá chính thức."
            ),
            "_interrupt_gate": None,
        }

    consent = state.get("handoff_consent") or {}
    if not consent.get("consent_granted"):
        return {
            "status": "ABSTAINED",
            "decision": "ABSTAIN",
            "abstain_reason": "MISSING_CONSENT",
            "_interrupt_gate": None,
        }

    parsed = HandoffConsentRequest(**consent)
    phone = parsed.customer_phone.strip()
    masked = (
        phone[:2] + "*" * max(len(phone) - 6, 0) + phone[-4:]
        if len(phone) >= 6
        else "*" * len(phone)
    )

    return {
        "status": "HANDED_OFF",
        "decision": "HANDOFF_CREATE_DOSSIER",
        "dossier_id": None,  # tầng API gán sau khi persist LeadDossier
        "dossier_payload": {
            "customer_name": parsed.customer_name,
            "customer_phone": parsed.customer_phone,
            "customer_phone_masked": masked,
            "customer_email": parsed.customer_email,
            "consent_scope": "PRE_SALES_ADVISORY_AND_SALES_CONTACT",
        },
        "agent_message": (
            f"Em đã ghi nhận yêu cầu kết nối chuyên viên bán hàng (SĐT {masked}). "
            "Chuyên viên sẽ phản hồi trong vòng 15 phút."
        ),
        "_interrupt_gate": None,
    }
