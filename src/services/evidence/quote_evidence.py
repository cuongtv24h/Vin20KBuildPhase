"""Bằng chứng cấp-luận-điểm (claim-level) cho Báo giá chính thức — C-04 / F4 / N-14B.

Vì sao có module này
--------------------
Màn duyệt của Manager (`ApprovalWorkspacePage`) đọc `GET /quotes/{quote_id}/evidence` để đối soát
từng luận điểm (Why / Why-not) với điều khoản gốc. Trước đây endpoint đó không tồn tại ⇒ Manager mở
báo giá chỉ thấy số liệu trần, không có chứng cứ, và lệnh "trình duyệt" của Sale dừng ở bản DRAFT.

Module này:
1. Dựng **danh sách claim** cho một báo giá từ (chính sách đang hiệu lực) × (3 phương án đã tính) ×
   (ràng buộc khách hàng) — mỗi claim mang toạ độ nguồn hoặc tham chiếu tới artifact tính toán.
2. Chạy **5 invariant của `EvidenceLinker` (N-14B)** trên từng luận điểm để ra trạng thái
   VERIFIED / CONDITIONAL / REJECTED / UNLINKED — không tự chế thêm bộ kiểm mới.
3. Phát hành **EvidenceBundle** tất định theo `(quote_id, quote_version)` và lưu vào
   `evidence_bundles` để tra cứu lại không cần cột phụ (bundle id tất định = không cần migration).
4. Cung cấp **checklist "sẵn sàng trình duyệt"** cho cổng `/{quote_id}/submit-review`.

Nguồn chính sách
----------------
DB là nguồn chính khi môi trường đã seed (`policies`/`policy_rules`); môi trường demo/test (SQLite
chưa seed) dùng **đúng canonical fixture mà Copilot và trang Chính sách đang dùng**
(`src.agents.copilot.grounding`) — nhờ vậy bảng duyệt và câu trả lời Copilot không bao giờ lệch nhau.
Provider được bơm từ ngoài (`policy_provider`) nên có thể thay bằng nguồn DB thật mà không sửa lõi.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import EvidenceBundleModel
from src.models.rag_schemas import AttributedPolicyEvidence, EvidenceCoordinate
from src.services.compliance.gate import ComplianceCheckRequest, ComplianceGate
from src.services.evidence.linker import EvidenceLinker

logger = logging.getLogger(__name__)

#: Kết luận tổng của bundle (khớp EvidenceDecisionStatus dùng trong PEC contracts).
DECISION_VERIFIED = "VERIFIED"
DECISION_CONDITIONAL = "CONDITIONAL"
DECISION_REJECTED = "REJECTED"
DECISION_ABSTAINED = "ABSTAINED"

#: Bundle hợp lệ để trình duyệt: bằng chứng đã đối chiếu (VERIFIED) hoặc có điều kiện kèm cảnh báo
#: (CONDITIONAL). REJECTED (mâu thuẫn điều khoản) và ABSTAINED (không có chính sách hiệu lực) thì chặn.
SUBMITTABLE_DECISIONS = frozenset({DECISION_VERIFIED, DECISION_CONDITIONAL})

#: Ánh xạ trạng thái linker (C-04) → `ClaimSupportStatus` của hợp đồng UI.
_LINKER_TO_SUPPORT: dict[str, str] = {
    "VERIFIED": "SUPPORTED",
    "CONDITIONAL": "PARTIALLY_SUPPORTED",
    "REJECTED": "CONTRADICTED",
    "UNLINKED": "UNSUPPORTED",
}

DEFAULT_MONTHLY_CAPACITY_VND = 0


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def bundle_id_for(quote_id: str, quote_version: int) -> str:
    """Bundle id tất định theo (quote, version) — tra cứu lại không cần thêm cột CSDL."""
    return f"EB-{_sha256_hex(f'{quote_id}:v{quote_version}')[:12]}"


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


@dataclass(slots=True)
class ReadinessItem:
    """Một mục trong checklist "bản chờ duyệt đã hoàn chỉnh chưa"."""

    key: str
    label: str
    ok: bool
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"key": self.key, "label": self.label, "ok": self.ok, "detail": self.detail}


@dataclass(slots=True)
class QuoteEvidenceResult:
    """Kết quả dựng bằng chứng cho một phiên bản báo giá."""

    bundle_id: str
    decision_status: str
    claims: list[dict[str, Any]]
    policy_id: str | None
    policy_version: str | None
    policy_snapshot_hash: str
    canonical_bundle_hash: str
    applied_rule_count: int
    conflict_pairs: list[dict[str, Any]]
    summary_text: str
    created_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "decision_status": self.decision_status,
            "claims": self.claims,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_snapshot_hash": self.policy_snapshot_hash,
            "canonical_bundle_hash": self.canonical_bundle_hash,
            "applied_rule_count": self.applied_rule_count,
            "conflict_pairs": self.conflict_pairs,
            "summary_text": self.summary_text,
            "created_at": self.created_at,
        }


def _default_policy_provider(project_id: str | None) -> list[dict[str, Any]]:
    """Nguồn chính sách mặc định: canonical fixture dùng chung với Copilot/trang Chính sách.

    Import muộn để (a) tránh vòng import services ↔ agents lúc nạp module, (b) cho phép môi trường
    production bơm provider đọc DB thật mà không đụng tới nhánh này.
    """
    from src.agents.copilot import grounding

    return grounding.list_policies(project_id)


def _split_section(section: str | None) -> tuple[str, str]:
    """`"Điều 4, Khoản 2b"` → `("Điều 4", "Khoản 2b")` cho `EvidenceCoordinate`."""
    parts = [p.strip() for p in str(section or "").split(",") if p.strip()]
    if not parts:
        return ("Điều ?", "Khoản ?")
    if len(parts) == 1:
        return (parts[0], "Khoản ?")
    return (parts[0], parts[1])


def _parse_iso_date(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value or "").strip()[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


class QuoteEvidenceService:
    """Dựng, lưu và kiểm tra bằng chứng cho một báo giá — nguồn dữ liệu cho màn duyệt."""

    def __init__(
        self,
        policy_provider: Callable[[str | None], list[dict[str, Any]]] | None = None,
        linker: EvidenceLinker | None = None,
        compliance_gate: ComplianceGate | None = None,
    ) -> None:
        self._policy_provider = policy_provider or _default_policy_provider
        self._linker = linker or EvidenceLinker()
        self._compliance = compliance_gate or ComplianceGate()

    # ------------------------------------------------------------------
    # 1. Chọn chính sách hiệu lực (time-travel filter cứng)
    # ------------------------------------------------------------------
    def resolve_active_policy(
        self,
        project_id: str | None,
        transaction_date: date | str | None,
    ) -> dict[str, Any] | None:
        """Chính sách đang hiệu lực tại ngày giao dịch; `None` nếu không có (⇒ ABSTAINED)."""
        tx_date = _parse_iso_date(transaction_date) or date.today()
        tx_iso = tx_date.isoformat()
        candidates = self._policy_provider(project_id)
        active: list[dict[str, Any]] = []
        for policy in candidates:
            if str(policy.get("status", "")).upper() in {"DRAFT", "REVOKED"}:
                continue
            if str(policy.get("effective_from", "0000-01-01")) <= tx_iso <= str(policy.get("effective_to", "9999-12-31")):
                active.append(policy)
        if not active:
            return None
        # Chính sách hiệu lực sau cùng (effective_from lớn nhất) là bản đang áp dụng.
        active.sort(key=lambda p: str(p.get("effective_from", "")), reverse=True)
        return active[0]

    # ------------------------------------------------------------------
    # 2. Dựng claim từ (chính sách × phương án × ràng buộc khách)
    # ------------------------------------------------------------------
    def _claim_records(
        self,
        policy: dict[str, Any] | None,
        scenarios: dict[str, Any],
        recommended_code: str | None,
        snapshot_payload: dict[str, Any],
        transaction_date: date,
    ) -> tuple[list[dict[str, Any]], list[str], int]:
        """Trả về (claims, vi phạm invariant, số rule có nguồn được đối chiếu)."""
        claims: list[dict[str, Any]] = []
        violations: list[str] = []
        applied_rule_count = 0
        rules: list[dict[str, Any]] = list((policy or {}).get("rules") or [])
        rules_by_code = {str(r.get("rule_code", "")).upper(): r for r in rules}
        rules_by_title = {self._norm(r.get("title")): r for r in rules if r.get("title")}

        # 2a. Ràng buộc khách hàng do Sale/Copilot nhập — nêu ra để Manager đối chiếu đầu vào.
        own_funds = int(snapshot_payload.get("own_funds_vnd") or 0)
        monthly = int(snapshot_payload.get("monthly_capacity_vnd") or 0)
        if own_funds or monthly:
            claims.append(
                {
                    "claim_id": "INPUT-001",
                    "claim_type": "USER_PROVIDED",
                    "direction": "WHY",
                    "text": (
                        "Đầu vào do Sale khai báo: vốn tự có "
                        f"{own_funds:,} VNĐ, khả năng chi trả hàng tháng {monthly:,} VNĐ."
                    ).replace(",", "."),
                    "support_status": "SUPPORTED",
                    "source_coordinates": [],
                    "calculation_refs": ["snapshot_payload.own_funds_vnd", "snapshot_payload.monthly_capacity_vnd"],
                    "unsupported_fragment": None,
                    "rule_code": None,
                    "decision_status": None,
                }
            )

        # 2b. Điều khoản của chính sách đang hiệu lực — lớp bằng chứng PHÁP LÝ có toạ độ nguồn.
        # Đây là phần bảo đảm "mỗi con số có điều khoản đứng sau", độc lập với việc engine đã áp
        # ưu đãi nào cho khách.
        for rule in rules:
            if str(rule.get("validation_status") or "APPROVED_FOR_USE").upper() not in {
                "APPROVED_FOR_USE",
                "ACTIVE",
                "PUBLISHED",
            }:
                continue
            support, status_violations = self._link_rule_claim(
                rule=rule,
                policy=policy or {},
                claim_id=f"POL-{rule.get('rule_code')}",
                claim_text=f"{rule.get('title', rule.get('rule_code'))}.",
                transaction_date=transaction_date,
            )
            violations.extend(status_violations)
            has_coordinate = bool((rule.get("source") or {}).get("quote"))
            if support == "SUPPORTED" and has_coordinate:
                applied_rule_count += 1
            claims.append(
                {
                    "claim_id": f"POL-{rule.get('rule_code')}",
                    "claim_type": "POLICY_REASON",
                    "direction": "WHY",
                    "text": (
                        f"Chính sách đang hiệu lực có điều khoản: {rule.get('title', rule.get('rule_code'))}"
                        f" — {rule.get('source', {}).get('section', '')}."
                    ).strip(),
                    "support_status": support if has_coordinate else "UNSUPPORTED",
                    "source_coordinates": [self._rule_coordinate(rule, policy or {})] if has_coordinate else [],
                    "calculation_refs": [],
                    "unsupported_fragment": None if has_coordinate else "source_coordinate",
                    "rule_code": rule.get("rule_code"),
                    "decision_status": "CONDITIONAL" if support == "PARTIALLY_SUPPORTED" else "ELIGIBLE",
                }
            )

        # 2c. Mỗi phương án: claim kết quả tính toán (máy) + đối chiếu ưu đãi engine đã áp.
        for code, detail in (scenarios or {}).items():
            if hasattr(detail, "model_dump"):
                detail = detail.model_dump(mode="json")
            if not isinstance(detail, dict):
                continue
            is_recommended = str(code) == str(recommended_code)
            claims.append(
                {
                    "claim_id": f"CALC-{code}",
                    "claim_type": "CALCULATION_RESULT",
                    "direction": "WHY" if is_recommended else "WHY_NOT",
                    "text": (
                        f"Phương án {code} ({detail.get('scenario_name', code)}): giá Net "
                        f"{int(detail.get('net_price_vnd') or 0):,} VNĐ · tổng HĐMB "
                        f"{int(detail.get('total_contract_price_vnd') or 0):,} VNĐ · đợt đầu "
                        f"{int(detail.get('initial_cash_outflow_vnd') or 0):,} VNĐ."
                    ).replace(",", "."),
                    "support_status": "SUPPORTED",
                    "source_coordinates": [],
                    "calculation_refs": [
                        f"scenarios.{code}.net_price_vnd",
                        f"scenarios.{code}.total_contract_price_vnd",
                        f"scenarios.{code}.initial_cash_outflow_vnd",
                    ],
                    "unsupported_fragment": None,
                    "rule_code": None,
                    "decision_status": None,
                }
            )

            for index, incentive in enumerate(detail.get("applied_incentives") or [], start=1):
                # Chỉ khớp CHÍNH XÁC theo mã rule hoặc tiêu đề điều khoản — không khớp mờ, vì gán
                # nhầm một ưu đãi sang điều khoản khác còn tệ hơn là nói thẳng "chưa map được".
                rule = rules_by_code.get(str(incentive).upper()) or rules_by_title.get(self._norm(incentive))
                claim_id = f"WHY-{code}-{index:02d}"
                if rule is None:
                    claims.append(
                        {
                            "claim_id": claim_id,
                            "claim_type": "POLICY_REASON",
                            "direction": "WHY",
                            "text": (
                                f"Engine áp ưu đãi '{incentive}' cho {code}; chưa đối chiếu được với một "
                                "điều khoản cụ thể trong chính sách đang hiệu lực — cần người rà lại."
                            ),
                            "support_status": "PARTIALLY_SUPPORTED",
                            "source_coordinates": [],
                            "calculation_refs": [f"scenarios.{code}.applied_incentives"],
                            "unsupported_fragment": str(incentive),
                            "rule_code": None,
                            "decision_status": None,
                        }
                    )
                    continue

                support, status_violations = self._link_rule_claim(
                    rule=rule,
                    policy=policy or {},
                    claim_id=claim_id,
                    claim_text=f"{rule.get('title', incentive)} áp dụng cho {code}.",
                    transaction_date=transaction_date,
                )
                violations.extend(status_violations)
                claims.append(
                    {
                        "claim_id": claim_id,
                        "claim_type": "POLICY_REASON",
                        "direction": "WHY",
                        "text": f"{rule.get('title', incentive)} ({incentive}) áp dụng cho {code}.",
                        "support_status": support,
                        "source_coordinates": [self._rule_coordinate(rule, policy or {})],
                        "calculation_refs": [f"scenarios.{code}.applied_incentives"],
                        "unsupported_fragment": None,
                        "rule_code": rule.get("rule_code"),
                        "decision_status": "CONDITIONAL" if support == "PARTIALLY_SUPPORTED" else "ELIGIBLE",
                    }
                )

        # 2d. Kết luận khuyến nghị — claim dẫn xuất, tham chiếu artifact xếp hạng.
        if recommended_code:
            claims.append(
                {
                    "claim_id": "REC-001",
                    "claim_type": "DERIVED_RECOMMENDATION",
                    "direction": "WHY",
                    "text": f"Hệ thống đề xuất {recommended_code} cho cấu hình tài chính đã khai báo.",
                    "support_status": "SUPPORTED",
                    "source_coordinates": [],
                    "calculation_refs": ["recommended_scenario_code"],
                    "unsupported_fragment": None,
                    "rule_code": None,
                    "decision_status": None,
                }
            )
        return claims, violations, applied_rule_count

    def _link_rule_claim(
        self,
        rule: dict[str, Any],
        policy: dict[str, Any],
        claim_id: str,
        claim_text: str,
        transaction_date: date,
    ) -> tuple[str, list[str]]:
        """Chạy 5 invariant N-14B của `EvidenceLinker` cho một điều khoản."""

        def _evidence(verbatim: str) -> AttributedPolicyEvidence:
            chunk = rule.get("source") or {}
            article, clause = _split_section(chunk.get("section"))
            return AttributedPolicyEvidence(
                coordinate=EvidenceCoordinate(
                    policy_id=str(policy.get("policy_id") or "POL-UNKNOWN"),
                    article=article,
                    clause=clause,
                    content_sha256=_sha256_hex(verbatim.strip()),
                ),
                policy_title=str(policy.get("title") or ""),
                verbatim_text=verbatim,
                valid_from=_parse_iso_date(policy.get("effective_from")) or date(2026, 1, 1),
                valid_to=_parse_iso_date(policy.get("effective_to")) or date(9999, 12, 31),
                applicability_conditions={
                    # Điều kiện đối tượng (cư dân, số căn…) là thông tin để Manager đối chiếu thêm.
                    # KHÔNG hạ claim xuống "có điều kiện" chỉ vì rule có điều kiện đối tượng: engine đã
                    # quyết định ưu đãi nào áp cho khách, còn claim ở đây nói về sự tồn tại + toạ độ
                    # của điều khoản. Không thì mọi báo giá ở dự án có rule cư dân đều bị CONDITIONAL oan.
                    "requires_management_approval": False,
                    "required_segments": rule.get("required_segments") or [],
                },
                similarity_score=1.0,
                is_superseded=str(policy.get("status", "")).upper() not in {"ACTIVE", "PUBLISHED", "APPROVED_FOR_USE"},
            )

        quote_text = str((rule.get("source") or {}).get("quote") or rule.get("title") or "").strip()
        if not quote_text:
            return "UNSUPPORTED", []

        result = self._linker.link_claim(
            claim_id=claim_id,
            claim_text=claim_text,
            candidate_evidences=[_evidence(quote_text)],
            transaction_date=transaction_date.isoformat(),
        )
        return _LINKER_TO_SUPPORT.get(result.status, "UNSUPPORTED"), list(result.reasons)

    @staticmethod
    def _rule_coordinate(rule: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
        """Toạ độ nguồn theo hợp đồng UI (`SourceCoordinate`)."""
        chunk = rule.get("source") or {}
        return {
            "document_id": chunk.get("document_id") or policy.get("document_id") or policy.get("policy_id") or "",
            "document_version": chunk.get("document_version") or policy.get("policy_version") or "",
            "document_hash": chunk.get("document_hash") or policy.get("document_hash") or "",
            "page": int(chunk.get("page") or 0),
            "section": chunk.get("section") or "",
            "clause_id": chunk.get("clause_id") or "",
            "quote": chunk.get("quote") or "",
            "policy_id": policy.get("policy_id"),
            "rule_code": rule.get("rule_code"),
        }

    @staticmethod
    def _norm(value: Any) -> str:
        return str(value or "").strip().lower()

    # ------------------------------------------------------------------
    # 3. Kết luận bundle + văn bản tóm tắt cho cổng F8
    # ------------------------------------------------------------------
    @staticmethod
    def _decision(claims: list[dict[str, Any]]) -> str:
        supports = {str(c.get("support_status")) for c in claims}
        if "CONTRADICTED" in supports:
            return DECISION_REJECTED
        if supports & {"PARTIALLY_SUPPORTED", "UNSUPPORTED"}:
            return DECISION_CONDITIONAL
        return DECISION_VERIFIED

    @staticmethod
    def _summary_text(policy: dict[str, Any] | None, scenarios: dict[str, Any], recommended_code: str | None) -> str:
        """Văn bản hướng khách hàng của báo giá — đầu vào cho cổng kiểm duyệt F8."""
        parts: list[str] = []
        if policy:
            parts.append(f"Chính sách áp dụng: {policy.get('title') or policy.get('policy_id')}.")
        for code, detail in (scenarios or {}).items():
            if hasattr(detail, "model_dump"):
                detail = detail.model_dump(mode="json")
            if not isinstance(detail, dict):
                continue
            parts.append(
                f"Phương án {code} ({detail.get('scenario_name', code)}): giá Net "
                f"{int(detail.get('net_price_vnd') or 0):,} VNĐ, tổng HĐMB "
                f"{int(detail.get('total_contract_price_vnd') or 0):,} VNĐ."
            )
        if recommended_code:
            parts.append(f"Đề xuất: {recommended_code}.")
        return " ".join(parts).replace(",", ".")

    def _policy_snapshot_hash(self, policy: dict[str, Any] | None) -> str:
        if not policy:
            return f"sha256:{_sha256_hex('no-active-policy')}"
        fingerprint = {
            "policy_id": policy.get("policy_id"),
            "policy_version": policy.get("policy_version"),
            "document_id": policy.get("document_id"),
            "document_hash": policy.get("document_hash"),
            "effective_from": str(policy.get("effective_from")),
            "effective_to": str(policy.get("effective_to")),
        }
        return f"sha256:{_sha256_hex(_canonical(fingerprint))}"

    # ------------------------------------------------------------------
    # 4. API công khai: dựng + lưu + đọc + checklist
    # ------------------------------------------------------------------
    def build(
        self,
        quote_id: str,
        quote_version: int,
        project_id: str | None,
        snapshot_payload: dict[str, Any],
    ) -> QuoteEvidenceResult:
        """Dựng bundle thuần (không ghi DB) — tách riêng để test và để tái dùng ở worker."""
        payload = snapshot_payload or {}
        tx_date = (
            _parse_iso_date(payload.get("transaction_date"))
            or _parse_iso_date(payload.get("quote_date"))
            or date.today()
        )
        scenarios = payload.get("scenarios") or {}
        recommended = payload.get("recommended_scenario_code")
        policy = self.resolve_active_policy(project_id, tx_date)

        if policy is None:
            claims = [
                {
                    "claim_id": "POLICY-000",
                    "claim_type": "POLICY_REASON",
                    "direction": "WHY",
                    "text": "Không tìm thấy văn bản chính sách nào hiệu lực tại ngày giao dịch — hệ thống không kết luận thay.",
                    "support_status": "UNSUPPORTED",
                    "source_coordinates": [],
                    "calculation_refs": ["transaction_date"],
                    "unsupported_fragment": "active_policy",
                    "rule_code": None,
                    "decision_status": None,
                }
            ]
            return QuoteEvidenceResult(
                bundle_id=bundle_id_for(quote_id, quote_version),
                decision_status=DECISION_ABSTAINED,
                claims=claims,
                policy_id=None,
                policy_version=None,
                policy_snapshot_hash=self._policy_snapshot_hash(None),
                canonical_bundle_hash=f"sha256:{_sha256_hex(_canonical(claims))}",
                applied_rule_count=0,
                conflict_pairs=[],
                summary_text="",
                created_at=datetime.now(UTC).isoformat(),
            )

        claims, violations, applied_rule_count = self._claim_records(
            policy, scenarios, recommended, payload, tx_date
        )
        decision = self._decision(claims)
        snapshot_hash = self._policy_snapshot_hash(policy)
        bundle_hash = f"sha256:{_sha256_hex(_canonical({'claims': claims, 'violations': sorted(set(violations))}))}"
        return QuoteEvidenceResult(
            bundle_id=bundle_id_for(quote_id, quote_version),
            decision_status=decision,
            claims=claims,
            policy_id=str(policy.get("policy_id") or ""),
            policy_version=str(policy.get("policy_version") or ""),
            policy_snapshot_hash=snapshot_hash,
            canonical_bundle_hash=bundle_hash,
            applied_rule_count=applied_rule_count,
            conflict_pairs=[{"violation": v} for v in sorted(set(violations))],
            summary_text=self._summary_text(policy, scenarios, recommended),
            created_at=datetime.now(UTC).isoformat(),
        )

    async def build_and_store(
        self,
        db: AsyncSession,
        quote_id: str,
        quote_version: int,
        project_id: str | None,
        snapshot_payload: dict[str, Any],
    ) -> QuoteEvidenceResult:
        """Dựng bundle rồi ghi vào `evidence_bundles` (idempotent theo quote+version)."""
        result = self.build(quote_id, quote_version, project_id, snapshot_payload)
        body = result.as_dict()
        body["quote_id"] = quote_id
        body["quote_version"] = quote_version
        body["project_id"] = project_id

        existing = await self.load(db, quote_id, quote_version)
        if existing is not None:
            existing.decision_status = result.decision_status
            existing.canonical_bundle_hash = result.canonical_bundle_hash
            existing.policy_snapshot_hash = result.policy_snapshot_hash
            existing.bundle_payload = body
            db.add(existing)
        else:
            db.add(
                EvidenceBundleModel(
                    bundle_id=result.bundle_id,
                    decision_status=result.decision_status,
                    canonical_bundle_hash=result.canonical_bundle_hash,
                    query_fingerprint=f"sha256:{_sha256_hex(f'{quote_id}:{quote_version}')}",
                    transaction_context_hash=f"sha256:{_sha256_hex(str(snapshot_payload.get('transaction_date') or ''))}",
                    policy_snapshot_hash=result.policy_snapshot_hash,
                    bundle_payload=body,
                )
            )
        await db.flush()
        return result

    async def load(self, db: AsyncSession, quote_id: str, quote_version: int) -> EvidenceBundleModel | None:
        """Đọc bundle đã phát hành cho đúng phiên bản báo giá."""
        stmt = select(EvidenceBundleModel).where(EvidenceBundleModel.bundle_id == bundle_id_for(quote_id, quote_version))
        return (await db.execute(stmt)).scalars().first()

    async def readiness(
        self,
        db: AsyncSession,
        quote: Any,
        snapshot_payload: dict[str, Any],
    ) -> tuple[bool, list[ReadinessItem]]:
        """Checklist "bản chờ duyệt hoàn chỉnh": 3 điều kiện cứng + bundle bằng chứng + F8."""
        items: list[ReadinessItem] = []
        version = int(getattr(quote, "quote_version", 1) or 1)

        scenarios = (snapshot_payload or {}).get("scenarios") or {}
        recommended = (snapshot_payload or {}).get("recommended_scenario_code")
        has_snapshot = bool(getattr(quote, "snapshot_hash", None))
        calc_ok = len(scenarios) >= 1 and bool(recommended) and has_snapshot
        items.append(
            ReadinessItem(
                key="calculated",
                label="Đã tính phương án & đóng băng snapshot",
                ok=calc_ok,
                detail=(
                    f"{len(scenarios)} phương án, đề xuất {recommended or '—'}"
                    if calc_ok
                    else "Chưa chạy /calculate (bản nháp chưa có phương án tài chính)"
                ),
            )
        )

        bundle = await self.load(db, str(getattr(quote, "quote_id", "")), version)
        bundle_status = str(bundle.decision_status) if bundle else "MISSING"
        applied_rules = int((bundle.bundle_payload or {}).get("applied_rule_count") or 0) if bundle else 0
        evidence_ok = bool(bundle) and bundle_status in SUBMITTABLE_DECISIONS and applied_rules >= 1
        if bundle is None:
            evidence_detail = "Chưa phát hành bộ chứng cứ cho phiên bản này — chạy POST /calculate trước."
        elif bundle_status == DECISION_ABSTAINED:
            evidence_detail = (
                "Không có văn bản chính sách hiệu lực cho dự án tại ngày giao dịch — hệ thống không "
                "kết luận thay; cần Policy Admin công bố chính sách hoặc rà lại ngày giao dịch."
            )
        elif applied_rules < 1:
            evidence_detail = f"Bộ chứng cứ {bundle_status} nhưng 0 điều khoản có toạ độ nguồn để đối chiếu."
        elif not evidence_ok:
            evidence_detail = f"Bộ chứng cứ {bundle_status} — mâu thuẫn điều khoản, không trình duyệt được."
        else:
            evidence_detail = f"{bundle_status} · {applied_rules} điều khoản có nguồn"
        items.append(
            ReadinessItem(
                key="evidence",
                label="Có bộ chứng cứ đối chiếu điều khoản",
                ok=evidence_ok,
                detail=evidence_detail,
            )
        )

        if bundle:
            summary = str((bundle.bundle_payload or {}).get("summary_text") or "")
            check = self._compliance.check(ComplianceCheckRequest(message=summary or "—", mode="ON_DRAFT"))
            blocked = str(getattr(check, "required_action", "")).startswith("BLOCK")
            items.append(
                ReadinessItem(
                    key="compliance",
                    label="Văn bản báo giá qua cổng kiểm duyệt F8",
                    ok=not blocked,
                    detail=f"{getattr(check, 'overall_status', '?')} · {getattr(check, 'required_action', '?')}",
                )
            )
        else:
            items.append(
                ReadinessItem(
                    key="compliance",
                    label="Văn bản báo giá qua cổng kiểm duyệt F8",
                    ok=False,
                    detail="Chưa có văn bản để kiểm duyệt",
                )
            )

        return all(i.ok for i in items), items


__all__ = [
    "QuoteEvidenceService",
    "QuoteEvidenceResult",
    "ReadinessItem",
    "bundle_id_for",
    "DECISION_VERIFIED",
    "DECISION_CONDITIONAL",
    "DECISION_REJECTED",
    "DECISION_ABSTAINED",
    "SUBMITTABLE_DECISIONS",
]
