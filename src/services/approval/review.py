"""
Quote Review and Approval Service (Spike 3)
Owner: TechLead (cuongtv_02560)
Zero-Trust Invariant:
1. Separation of Duties (SoD): Creator != Approver
2. Atomic Commit-Discard: RAM signature discarded on DB failure, zero orphan signatures.
3. Outbox Event Generation: Persisted in same ACID transaction.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.contracts.enums import ApprovalStatus, PdfStatus, QuoteWorkflowStatus
from src.contracts.errors import DomainError, ErrorCode
from src.db.models import QuoteModel, TransactionalOutboxModel
from src.services.approval.signing import KMSServerSigner
from src.services.audit.chain import AuditChainEngine


class QuoteApprovalService:
    """
    Service governing official quote approval lifecycle and atomic cryptographic attestation.
    """

    def __init__(
        self,
        kms_signer: KMSServerSigner | None = None,
        audit_chain: AuditChainEngine | None = None,
    ) -> None:
        self.kms_signer = kms_signer or KMSServerSigner()
        self.audit_chain = audit_chain or AuditChainEngine()

    @staticmethod
    def validate_separation_of_duties(creator_id: str, approver_id: str) -> None:
        """
        Enforce Zero-Trust Invariant: The salesperson who created the quote
        cannot approve or attest their own quote.
        """
        if creator_id == approver_id:
            raise DomainError(
                ErrorCode.SOD_VIOLATION,
                "Separation of Duties violation: The creator of a quote cannot approve it.",
                details={"creator_id": creator_id, "approver_id": approver_id},
            )

    async def execute_atomic_approval(
        self,
        db_session: AsyncSession,
        quote_id: str,
        approver_id: str,
        snapshot_data: dict[str, Any],
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        """
        Execute atomic approval with KMS attestation and outbox queuing.
        All database operations happen in a single ACID transaction.
        If database fails/rolls back, RAM signature is discarded, preventing orphan signatures.
        """
        # Fetch quote
        stmt = select(QuoteModel).where(QuoteModel.quote_id == quote_id)
        result = await db_session.execute(stmt)
        quote = result.scalars().first()

        if quote is None:
            raise DomainError(
                ErrorCode.QUOTE_NOT_FOUND,
                f"Quote '{quote_id}' does not exist.",
                details={"quote_id": quote_id},
            )

        # 1. Enforce Separation of Duties
        self.validate_separation_of_duties(quote.created_by, approver_id)

        # 2. Check optimistic concurrency / version
        if expected_version is not None and quote.quote_version != expected_version:
            raise DomainError(
                ErrorCode.VERSION_CONFLICT,
                f"Quote version conflict: expected {expected_version}, current {quote.quote_version}.",
                details={"expected_version": expected_version, "current_version": quote.quote_version},
            )

        # 3. Check allowed transition states
        if quote.status not in (
            QuoteWorkflowStatus.READY_FOR_REVIEW.value,
            QuoteWorkflowStatus.CALCULATING.value,
            QuoteWorkflowStatus.NEEDS_REVISION.value,
            QuoteWorkflowStatus.DRAFT.value,
            QuoteWorkflowStatus.READY_FOR_REVIEW,
            QuoteWorkflowStatus.CALCULATING,
            QuoteWorkflowStatus.NEEDS_REVISION,
            QuoteWorkflowStatus.DRAFT,
        ):
            raise DomainError(
                ErrorCode.INVALID_STATE_TRANSITION,
                f"Cannot approve quote in workflow status '{quote.status}'.",
                details={"status": quote.status},
            )

        # 4. Cryptographic attestation in RAM
        snapshot_hash = self.kms_signer.calculate_snapshot_hash(snapshot_data)
        signature_b64 = self.kms_signer.sign_snapshot_hash(snapshot_hash)

        # 5. Persist quote changes in DB
        now_utc = datetime.now(UTC)
        quote.approval_status = ApprovalStatus.APPROVED.value
        quote.status = QuoteWorkflowStatus.APPROVED.value
        quote.pdf_status = PdfStatus.PENDING.value
        quote.approved_by = approver_id
        quote.signature = signature_b64
        quote.snapshot_hash = snapshot_hash
        quote.updated_at = now_utc

        # 6. Record audit event in anti-cyclic hash chain
        await self.audit_chain.append_event(
            db_session=db_session,
            quote_id=quote_id,
            event_type="QUOTE_APPROVED",
            actor_id=approver_id,
            payload={
                "snapshot_hash": snapshot_hash,
                "signature": signature_b64,
                "approver_id": approver_id,
                "approved_at": now_utc.isoformat(),
            },
        )

        # 7. Enqueue transactional outbox event for async PDF generation
        outbox_event = TransactionalOutboxModel(
            event_id=str(uuid4()),
            aggregate_type="QUOTE",
            aggregate_id=quote_id,
            event_type="OFFICIAL_QUOTE_ISSUED",
            payload_json={
                "quote_id": quote_id,
                "signature": signature_b64,
                "snapshot_hash": snapshot_hash,
                "approved_by": approver_id,
            },
            status="PENDING",
            retry_count=0,
            created_at=now_utc,
        )
        db_session.add(outbox_event)

        # Returns summary for caller. Notice: caller commits the db_session.
        return {
            "quote": quote,
            "quote_id": quote_id,
            "status": ApprovalStatus.APPROVED,
            "signature": signature_b64,
            "snapshot_hash": snapshot_hash,
            "approved_by": approver_id,
            "approved_at": now_utc.isoformat(),
        }

    async def execute_rejection(
        self,
        db_session: AsyncSession,
        quote_id: str,
        approver_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """
        Reject a quote with reason logged into the tamper-evident audit trail.
        """
        stmt = select(QuoteModel).where(QuoteModel.quote_id == quote_id)
        result = await db_session.execute(stmt)
        quote = result.scalars().first()

        if quote is None:
            raise DomainError(ErrorCode.QUOTE_NOT_FOUND, f"Quote '{quote_id}' does not exist.")

        self.validate_separation_of_duties(quote.created_by, approver_id)

        # Guard: Cannot reject an already APPROVED or signed quote
        if (
            quote.approval_status == ApprovalStatus.APPROVED.value
            or quote.status == QuoteWorkflowStatus.APPROVED.value
            or quote.signature is not None
        ):
            raise DomainError(
                ErrorCode.INVALID_STATE_TRANSITION,
                f"Cannot reject quote '{quote_id}' that has already been approved and signed.",
                details={"status": quote.status, "approval_status": quote.approval_status},
            )

        now_utc = datetime.now(UTC)
        quote.approval_status = ApprovalStatus.REJECTED.value
        quote.status = QuoteWorkflowStatus.REJECTED.value

        await self.audit_chain.append_event(
            db_session=db_session,
            quote_id=quote_id,
            event_type="QUOTE_REJECTED",
            actor_id=approver_id,
            payload={
                "reason": reason,
                "rejected_by": approver_id,
                "rejected_at": now_utc.isoformat(),
            },
        )

        return {
            "quote_id": quote_id,
            "status": ApprovalStatus.REJECTED,
            "rejected_by": approver_id,
            "reason": reason,
        }
