"""Node HITL, ký số & commit (N-15 → N-20)."""

from src.agents.official_quote.state import OfficialQuoteState


async def build_approval_package(state: OfficialQuoteState) -> dict:
    """N-15 — Pure Logic.

    Đóng gói hồ sơ HITL: bảng đối đầu 3 phương án, cờ rủi ro Đỏ/Vàng/Xanh,
    giải trình Why/Why-not. Chuyển `READY_FOR_REVIEW`.
    """
    raise NotImplementedError("C-01/N-15: theo TD-4.3 — approval package")


async def interrupt_human_review(state: OfficialQuoteState) -> dict:
    """N-16 — Interrupt Boundary 2 (HITL).

    LangGraph dừng, checkpoint PostgreSQL, chờ `HumanReviewDecision`.
    Kiểm tra resume token, deadline, stale quote version.
    """
    raise NotImplementedError("C-01/N-16: theo TD-4.3 — human review interrupt")


async def create_new_quote_revision(state: OfficialQuoteState) -> dict:
    """N-17 — Pure State Mutation.

    Version cũ → `SUPERSEDED` (append-only `QUOTE_VERSION_SUPERSEDED`),
    tạo version mới (`quote_version + 1`) chạy lại từ N-01.
    """
    raise NotImplementedError("C-01/N-17: theo TD-4.3 — revision")


async def create_exception_version(state: OfficialQuoteState) -> dict:
    """N-18 — Pure State Mutation (Interrupt Boundary 3: Exception Input).

    Giữ V1 `ABSTAINED`, tạo V2 kèm `ExceptionApprovalRecord` (ủy quyền TGĐ),
    quay lại N-06.
    """
    raise NotImplementedError("C-01/N-18: theo TD-4.3 — exception version")


async def freeze_approval_intent(state: OfficialQuoteState) -> dict:
    """N-19A — Deterministic Pre-Check.

    Đóng băng `approval_intent_id`, `approval_payload_hash = SHA256(canonical_json)`,
    `approval_created_at_frozen` TRƯỚC khi gọi KMS.
    Dùng: `src.contracts.common.canonical_json_bytes`.
    """
    raise NotImplementedError("C-01/N-19A: theo TD-4.3 — freeze intent")


async def request_server_attestation(state: OfficialQuoteState) -> dict:
    """N-19B — Pre-Commit Side Effect.

    Xác thực OTP Quản lý → KMS Server Signer ký Ed25519 (RFC 8032) trên hash
    đã đóng băng. KMS timeout → `APPROVAL_FAILED`. Dùng: `src.services.approval.signing`.
    """
    raise NotImplementedError("C-01/N-19B: theo TD-4.3 — KMS attestation")


async def commit_atomic_transaction(state: OfficialQuoteState) -> dict:
    """N-20 — Database Side Effect.

    MỘT transaction duy nhất: (1) lưu Snapshot; (2) ghi `quote_audit_events`
    (hash chain C-07); (3) `APPROVED`; (4) insert `transactional_outbox`.
    DB fail → discard signature. Dùng: `src.db.repositories`.
    """
    raise NotImplementedError("C-01/N-20: theo TD-4.3 — atomic commit")
