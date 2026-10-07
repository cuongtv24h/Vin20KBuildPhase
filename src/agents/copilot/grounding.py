"""Nguồn dữ liệu nền (grounding) cho Sales Copilot.

Nguyên tắc: Copilot chỉ được nói điều có thật trong hệ thống. Module này là lớp
truy cập dữ liệu canonical (chính sách, giỏ hàng) dùng chung cho các tool.

- Ưu tiên PEC-RAG / DB khi có dữ liệu đã seed.
- Khi môi trường demo chưa seed (SQLite trống, không có API key) → dùng fixture
  canonical của `catalog.py` (POLICIES_DATA / UNITS_DATA) làm nguồn dự phòng.
"""

from __future__ import annotations

import logging
import unicodedata
from datetime import date
from typing import Any

from src.api.endpoints.catalog import POLICIES_DATA, UNITS_DATA
from src.contracts.units import BEDROOMS_BY_UNIT_TYPE, merge_units


def normalize(text: str) -> str:
    """Chuẩn hóa tiếng Việt: bỏ dấu, lowercase — dùng cho so khớp từ khóa."""
    if not text:
        return ""
    lowered = text.lower()
    decomposed = unicodedata.normalize("NFD", lowered)
    without_marks = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return without_marks.replace("đ", "d")


def format_vnd(amount: int | float | None) -> str:
    """Định dạng VNĐ kiểu Việt Nam: 4.655.200.000 ₫."""
    if amount is None:
        return "—"
    return f"{int(amount):,}".replace(",", ".") + " ₫"


def list_policies(project_id: str | None = None) -> list[dict[str, Any]]:
    """Danh sách chính sách canonical (có thể lọc theo dự án)."""
    if not project_id:
        return list(POLICIES_DATA)
    wanted = normalize(project_id)
    return [p for p in POLICIES_DATA if normalize(str(p.get("project_id", ""))) == wanted]


def resolve_active_policy(project_id: str | None, as_of: date | None = None) -> dict[str, Any] | None:
    """Chọn chính sách đang hiệu lực tại `as_of` cho dự án (time-travel filter cứng)."""
    tx_date = (as_of or date.today()).isoformat()
    candidates = list_policies(project_id)
    active = [
        p
        for p in candidates
        if str(p.get("effective_from", "0000-01-01")) <= tx_date <= str(p.get("effective_to", "9999-12-31"))
    ]
    if active:
        return active[0]
    return None


def policy_citations(policy: dict[str, Any], rules: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Sinh citation từ policy + các rule liên quan (dùng cho Evidence/Căn cứ)."""
    out: list[dict[str, Any]] = []
    for rule in rules or list(policy.get("rules", [])):
        src = rule.get("source") or {}
        out.append(
            {
                "policy_id": policy.get("policy_id"),
                "policy_version": policy.get("policy_version"),
                "policy_title": policy.get("title"),
                "rule_code": rule.get("rule_code"),
                "section": src.get("section"),
                "clause_id": src.get("clause_id"),
                "quote": src.get("quote"),
                "document_id": src.get("document_id") or policy.get("document_id"),
                "document_hash": src.get("document_hash") or policy.get("document_hash"),
                "effective_from": policy.get("effective_from"),
                "effective_to": policy.get("effective_to"),
                "source": "CANONICAL_FIXTURE",
            }
        )
    return out


def find_rules_by_keyword(keyword: str, project_id: str | None = None) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Tìm rule theo từ khóa (đã bỏ dấu) trên title + quote + rule_code."""
    key = normalize(keyword)
    tokens = [t for t in key.split() if len(t) >= 2]
    hits: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for policy in list_policies(project_id):
        for rule in policy.get("rules", []):
            haystack = normalize(
                " ".join(
                    [
                        str(rule.get("rule_code", "")),
                        str(rule.get("title", "")),
                        str((rule.get("source") or {}).get("quote", "")),
                        str((rule.get("source") or {}).get("section", "")),
                    ]
                )
            )
            score = sum(1 for t in tokens if t in haystack)
            if score > 0:
                hits.append((policy, rule))
    return hits


logger = logging.getLogger(__name__)

_cached_db_units: list[dict[str, Any]] | None = None
_cached_db_project_names: dict[str, str] = {}

def _fetch_db_units() -> list[dict[str, Any]]:
    """Đọc giỏ hàng THẬT từ DB (bảng `units` nối `projects`) — chỉ lấy trường có thật.

    Từ đợt 20 bảng `units` có thêm `area_m2` và `view`; căn nào chưa điền thì trả None (UI hiện "—"),
    không suy diễn theo loại căn.
    """
    global _cached_db_units
    if _cached_db_units is not None:
        return _cached_db_units
    try:
        import psycopg

        from src.config import get_settings

        settings = get_settings()
        db_url = settings.database_url.replace("+asyncpg", "")
        if not db_url.startswith(("postgres://", "postgresql://")):
            # SQLite (mặc định khi chạy local/test) không có bảng `units` thật ⇒ dùng fixture, không log lỗi.
            return []
        with psycopg.connect(db_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT u.unit_code, u.project_id, p.project_name, u.floor_number,
                           u.unit_type, u.listed_price_before_tax_vnd, u.status, u.area_m2, u.view
                    FROM units u
                    LEFT JOIN projects p ON p.project_id = u.project_id;
                """)
                rows = cur.fetchall()
                units: list[dict[str, Any]] = []
                for (
                    unit_code,
                    project_id,
                    project_name,
                    floor_number,
                    unit_type,
                    price,
                    status,
                    area_m2,
                    view,
                ) in rows:
                    name = str(project_name or "").strip() or str(project_id or "")
                    if project_id:
                        _cached_db_project_names[str(project_id)] = name
                    units.append(
                        {
                            "unit_code": unit_code,
                            "project_id": project_id,
                            "project_name": name,
                            "floor": floor_number,
                            "bedrooms": BEDROOMS_BY_UNIT_TYPE.get(str(unit_type or "").upper(), 0),
                            # Hai trường có thật trong DB từ đợt 20; dữ liệu cũ chưa điền thì để None
                            # (hiển thị "—") — tuyệt đối không suy diễn lại theo loại căn.
                            "area_m2": float(area_m2) if area_m2 else None,
                            "view": str(view or "").strip() or None,
                            "listed_price_before_tax_vnd": price,
                            "status": status,
                        }
                    )
                _cached_db_units = units
                return units
    except Exception as exc:
        logger.warning("Could not load units from DB: %s", exc)
        return []


def list_units() -> list[dict[str, Any]]:
    """Giỏ hàng đang dùng: **DB thật là nguồn chính**, fixture chỉ bù cho dự án DB chưa có.

    Lỗi cũ: cộng thẳng DB (40 căn) với fixture (4 căn) ⇒ giỏ hàng báo 44 căn, và Sale đọc thấy căn demo
    lẫn căn thật. Quy tắc gộp nằm ở `src.contracts.units.merge_units` để API cũng dùng đúng một luật.
    """
    return merge_units(_fetch_db_units(), UNITS_DATA)


def find_unit(unit_code: str | None) -> dict[str, Any] | None:
    if not unit_code:
        return None
    wanted = normalize(unit_code).replace(" ", "")
    for unit in list_units():
        if normalize(str(unit.get("unit_code"))).replace(" ", "") == wanted:
            return unit
    return None


def search_units(
    bedrooms: int | None = None,
    max_price_vnd: int | None = None,
    project_id: str | None = None,
    only_available: bool = True,
) -> list[dict[str, Any]]:
    results = []
    for unit in list_units():
        if only_available and unit.get("status") != "AVAILABLE":
            continue
        if bedrooms and int(unit.get("bedrooms", 0)) != bedrooms:
            continue
        if max_price_vnd and int(unit.get("listed_price_before_tax_vnd", 0)) > max_price_vnd:
            continue
        if project_id and normalize(str(unit.get("project_id"))) != normalize(project_id):
            continue
        results.append(unit)
    results.sort(key=lambda u: int(u.get("listed_price_before_tax_vnd", 0)))
    return results


def project_name(project_id: str | None) -> str:
    """Tên dự án: ưu tiên tên THẬT đọc từ DB, rồi tới nhãn fixture, cuối cùng trả chính mã dự án.

    Không bịa tên dự án: dự án chỉ có trong DB sẽ hiện đúng tên trong bảng `projects`.
    """
    key = str(project_id or "")
    if key in _cached_db_project_names:
        return _cached_db_project_names[key]
    mapping = {
        "THE_ZEN_PARK": "The Zen Park",
        "VLANDFUTURE_SAPPHIRE": "VLandFuture Sapphire",
        # Dự án VLF cũ chỉ còn trong catalog fixture (không có bảng `projects` tương ứng) — giữ để
        # tài liệu/demo cũ không vỡ, nhưng hỏi DB trước nên tên thật luôn thắng.
        "PROJECT-VLF-001": "VLand Future Riverside",
    }
    return mapping.get(key, key or "VLandFuture")

