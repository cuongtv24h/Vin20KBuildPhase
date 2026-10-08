"""Nguồn chính sách THẬT (bảng `policies` + `policy_atoms` trong PostgreSQL).

Vì sao có file này: **một** hàm dựng chính sách dùng chung cho cả hai đường đọc —

- `src/api/endpoints/catalog.py` (async, SQLAlchemy) cho trang Chính sách / danh mục;
- `src/agents/copilot/grounding.py` (sync, psycopg) cho Copilot và bộ chứng cứ báo giá.

Trước đây Copilot đọc fixture canonical còn trang Chính sách đọc DB ⇒ cùng một câu hỏi có thể ra
hai số liệu khác nhau, và bản chạy thật vẫn tư vấn bằng văn bản cứng. Nay cả hai đường cùng chạy
trên đúng hai bảng này; fixture chỉ còn dùng khi bật cờ `ALLOW_FIXTURE_DATA` (mặc định TẮT).

Cách dựng rule từ atom giữ nguyên như bản cũ trong `catalog.fetch_db_policies` để không đổi hành vi
của trang Chính sách — chỉ chuyển sang một chỗ duy nhất.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

logger = logging.getLogger(__name__)

POLICY_SQL = """
    SELECT policy_id, policy_name, version, effective_from, effective_to, status,
           document_hash, source_path, metadata_json, created_at
    FROM policies
    ORDER BY effective_from DESC, policy_id ASC
"""

ATOM_SQL = """
    SELECT atom_id, policy_id, atom_type, chapter, article, clause, point,
           line_start, line_end, canonical_text, retrieval_text, content_hash,
           valid_from, valid_to, customer_tiers, service_codes
    FROM policy_atoms
    ORDER BY line_start ASC, atom_id ASC
"""


def _get(row: Any, key: str, default: Any = None) -> Any:
    """Đọc một trường từ dict (psycopg) hoặc Row/ORM object (SQLAlchemy) mà không phân biệt nguồn."""
    if isinstance(row, Mapping):
        return row.get(key, default)
    return getattr(row, key, default)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _classify_rule(text_lower: str) -> tuple[str, float | None, int | None, list[str]]:
    """Suy ra loại ưu đãi từ nội dung atom — giữ nguyên luật của bản `fetch_db_policies` cũ."""
    kind = "DISCRETIONARY"
    discount_rate: float | None = None
    interest_support_months: int | None = None
    scenarios = ["PA-CHUDONG"]
    if "chiết khấu" in text_lower or "giảm giá" in text_lower:
        kind = "PERCENT_DISCOUNT"
        discount_rate = 0.08 if "8" in text_lower else (0.1 if "10" in text_lower else 0.05)
        scenarios = ["PA-NHANH"]
    elif "lãi suất" in text_lower or "ngân hàng" in text_lower or "vay" in text_lower:
        kind = "BANK_SUPPORT"
        interest_support_months = 24 if "24" in text_lower else 12
        scenarios = ["PA-VAY"]
    elif "quà" in text_lower or "nội thất" in text_lower:
        kind = "GIFT"
        scenarios = ["PA-CHUDONG", "PA-NHANH"]
    return kind, discount_rate, interest_support_months, scenarios


def build_policies_from_rows(
    policy_rows: Iterable[Any],
    atom_rows: Iterable[Any],
) -> list[dict[str, Any]]:
    """Dựng danh sách chính sách (kèm rules) từ hai bảng đã đọc — **nguồn: CSDL thật**.

    Trả về đúng cấu trúc mà các tool Copilot và trang Chính sách đang dùng:
    `policy_id / policy_version / title / project_id / status / effective_from / effective_to /
    document_id / document_hash / source_document / created_at / created_by / published_at /
    published_by / rules[]`, mỗi rule có `rule_code / title / kind / discount_rate /
    interest_support_months / applicable_scenarios / source{...}`.
    """
    atoms_by_policy: dict[str, list[Any]] = {}
    for atom in atom_rows:
        pid = str(_get(atom, "policy_id") or "")
        atoms_by_policy.setdefault(pid, []).append(atom)

    result: list[dict[str, Any]] = []
    for policy in policy_rows:
        pid = str(_get(policy, "policy_id") or "")
        if not pid:
            continue
        raw_meta = _get(policy, "metadata_json") or {}
        meta: dict[str, Any] = raw_meta if isinstance(raw_meta, Mapping) else {}
        version = _get(policy, "version") or "v1.0"
        document_hash = _get(policy, "document_hash")
        policy_status = str(_get(policy, "status") or "")

        rules: list[dict[str, Any]] = []
        for idx, atom in enumerate(atoms_by_policy.get(pid, []), 1):
            article = _get(atom, "article") or ""
            clause = _get(atom, "clause") or ""
            rule_title = f"{article} {clause}".strip() or f"Điều khoản {idx}"
            canonical_text = str(_get(atom, "canonical_text") or "")
            kind, discount_rate, interest_support_months, scenarios = _classify_rule(canonical_text.lower())
            rules.append(
                {
                    "rule_code": f"{pid}_R{idx:02d}",
                    "title": rule_title,
                    "kind": kind,
                    "discount_rate": discount_rate,
                    "cash_equivalent_vnd": None,
                    "interest_support_months": interest_support_months,
                    "applicable_scenarios": scenarios,
                    "required_segments": None,
                    "min_units_purchased": None,
                    "relations": [],
                    "is_ambiguous": False,
                    "is_selectable": True,
                    "validation_status": "APPROVED_FOR_USE",
                    "source": {
                        "document_id": f"DOC-{pid}",
                        "document_version": version,
                        "document_hash": _get(atom, "content_hash"),
                        "clause_id": clause or article or _get(atom, "atom_id"),
                        "section": article or "Quy định chung",
                        "page": _get(atom, "line_start") or 1,
                        "quote": canonical_text[:250],
                    },
                }
            )

        result.append(
            {
                "policy_id": pid,
                "policy_version": version,
                "title": _get(policy, "policy_name") or pid,
                "project_id": meta.get("project_id") or "PROJECT-VLF-001",
                "status": "PUBLISHED" if policy_status == "ACTIVE" else policy_status,
                "effective_from": _iso(_get(policy, "effective_from")) or "2026-01-01",
                "effective_to": _iso(_get(policy, "effective_to")) or "2026-12-31",
                "document_id": f"DOC-{pid}",
                "document_hash": document_hash,
                "source_document": _get(policy, "source_path") or f"{pid}.md",
                "created_at": _iso(_get(policy, "created_at")) or "2026-01-01T08:00:00Z",
                "created_by": {"user_id": "USR-ADM-001", "full_name": "Trần Chí Vĩ", "role": "POLICY_ADMIN"},
                "published_at": "2026-01-05T09:00:00Z",
                "published_by": {"user_id": "USR-MGR-001", "full_name": "Quản lý kinh doanh", "role": "MANAGER"},
                "data_source": "DB",
                "rules": rules,
            }
        )
    return result


_cache: list[dict[str, Any]] | None = None


def reset_cache() -> None:
    """Xoá cache trong tiến trình (dùng cho test/admin sau khi sửa chính sách)."""
    global _cache
    _cache = None


def fetch_policies_sync() -> list[dict[str, Any]]:
    """Đọc chính sách thật từ PostgreSQL bằng psycopg (sync) — dùng cho Copilot.

    Trả `[]` khi chưa cấu hình DB Postgres (ví dụ SQLite lúc chạy test) hoặc khi đọc lỗi; **không**
    thay bằng dữ liệu mẫu — nơi gọi phải nói thẳng là chưa có dữ liệu.
    """
    global _cache
    if _cache is not None:
        return _cache
    try:
        import psycopg

        from src.config import get_settings

        db_url = str(get_settings().database_url or "").replace("+asyncpg", "")
        if not db_url.startswith(("postgres://", "postgresql://")):
            return []
        with psycopg.connect(db_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(POLICY_SQL)
                policy_rows = cur.fetchall()
                cur.execute(ATOM_SQL)
                atom_rows = cur.fetchall()
        policies = build_policies_from_rows(policy_rows, atom_rows)
        _cache = policies
        return policies
    except Exception as exc:  # noqa: BLE001 — thiếu DB không được làm sập Copilot
        logger.warning("Không đọc được chính sách từ CSDL: %s", exc)
        return []


def policies_from_async_rows(policy_rows: Sequence[Any], atom_rows: Sequence[Any]) -> list[dict[str, Any]]:
    """Bản dùng cho đường async (SQLAlchemy Row) — chỉ để API gọi cho gọn."""
    return build_policies_from_rows(policy_rows, atom_rows)


__all__ = [
    "ATOM_SQL",
    "POLICY_SQL",
    "build_policies_from_rows",
    "fetch_policies_sync",
    "policies_from_async_rows",
    "reset_cache",
]
