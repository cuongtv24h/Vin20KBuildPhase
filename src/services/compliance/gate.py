"""F8 — Evidence-Backed Message Composer & Compliance Gate.

3 checkpoint (ON_PREVIEW, ON_COPY, ON_FINAL_SEND) × 4 tier
(`src.contracts.enums.ComplianceTier`). `POST /api/v1/messages/send` là
điểm phát hành DUY NHẤT và bắt buộc qua gate ON_FINAL_SEND.
"""

from src.contracts.enums import ComplianceCheckTrigger


class ComplianceGate:
    """Kiểm tra tin nhắn Sale trước khi cho phép gửi cho khách."""

    def __init__(self, triggers: tuple[ComplianceCheckTrigger, ...] = (ComplianceCheckTrigger.ON_FINAL_SEND,)):
        self.triggers = triggers

    async def check(self, message_text: str, context: dict) -> dict:
        """Trả về `MessageVerdict`: tier + vi phạm + evidence anchors.

        Phân loại theo fixtures: SUPPORTED / CONDITIONAL / UNSUPPORTED /
        PROHIBITED (`mydoc/dataset/fixtures/compliance_messages.json`).
        """
        raise NotImplementedError("C-11/F8: compliance check")
