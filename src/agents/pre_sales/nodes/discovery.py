"""
Pre-Sales advisory nodes: PS-01 (Init) và PS-02 (Input Collector).
Owner: Phase 2 — Pre-Sales Advisory StateGraph (C-09)
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from src.agents.pre_sales.state import PreSalesState

SESSION_TTL_SECONDS = 1800  # TTL phiên chat Pre-Sales theo spec C-09

WELCOME_MESSAGE = (
    "Xin chào Quý khách! Em là trợ lý tư vấn ảo của VlandFuture. "
    "Để em gợi ý phương án tài chính phù hợp nhất, anh/chị vui lòng cho em biết: "
    "(1) dự án và loại căn đang quan tâm, "
    "(2) số vốn tự có dự kiến, "
    "(3) khả năng trả góp hàng tháng, "
    "(4) thời điểm dự kiến nhận nhà."
)

FIELD_KEYWORDS: list[tuple[str, list[str]]] = [
    # (trường CustomerConstraints, từ khóa nhận diện trong lời nhắn)
    ("preferred_unit_code", ["căn", "unit", "căn hộ", "chung cư"]),
    ("project_id", ["dự án", "project", "beverly", "vland"]),
    ("own_funds_vnd", ["vốn", "tiền mặt", "own funds", "tự có"]),
    ("monthly_capacity_vnd", ["thu nhập", "trả góp", "hàng tháng", "monthly"]),
    ("unit_type", ["studio", "1br", "2br", "3br", "phòng ngủ"]),
]


# Số + đơn vị: '2 tỷ', '2tỷ', '1.5 tỷ', '1,5 tỷ', '500 triệu', '500triệu', '40 tr'
_AMOUNT_WITH_UNIT = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(tỷ|ty|triệu|tr)\b", re.IGNORECASE
)
# Số trần có/không phân cách nghìn: '2000000000', '2,000,000,000', '2.000.000.000'
_PLAIN_NUMBER = re.compile(r"\d{6,}")
_THOUSANDS_SEP = re.compile(r"(?<=\d)[.,](?=\d{3}(?:[.,]\d{3})*(?!\d))")

_UNIT_MULTIPLIERS = {
    "tỷ": 1_000_000_000,
    "ty": 1_000_000_000,
    "triệu": 1_000_000,
    "tr": 1_000_000,
}


def extract_amounts(text: str) -> list[tuple[int, int]]:
    """
    Trích xuất TẤT CẢ số tiền VNĐ trong văn bản, giữ vị trí ký tự để map theo ngữ cảnh.
    Hỗ trợ: '2 tỷ', '2tỷ', '1.5 tỷ', '1,5 tỷ', '500 triệu', '500triệu', '40 tr',
    '2000000000', '2,000,000,000', '2.000.000.000'.
    Trả về list (position, value) theo thứ tự xuất hiện. Không tính toán tài chính.
    """
    lowered = text.lower()
    found: list[tuple[int, int]] = []
    for m in _AMOUNT_WITH_UNIT.finditer(lowered):
        num = float(m.group(1).replace(",", "."))
        mul = _UNIT_MULTIPLIERS[m.group(2).lower()]
        found.append((m.start(), int(num * mul)))
    if found:
        return found
    for m in _PLAIN_NUMBER.finditer(_THOUSANDS_SEP.sub("", lowered)):
        # Vị trí xấp xỉ theo chuỗi gốc (đủ dùng cho mapping ngữ cảnh)
        found.append((m.start(), int(m.group(0))))
    return found


def parse_amount_vnd(text: str) -> int | None:
    """Trích xuất số tiền VNĐ ĐẦU TIÊN trong văn bản; None nếu không có."""
    amounts = extract_amounts(text)
    return amounts[0][1] if amounts else None


def _keyword_positions(lowered: str, keywords: tuple[str, ...]) -> list[int]:
    """Tất cả vị trí xuất hiện của bất kỳ từ khóa nào trong nhóm."""
    positions: list[int] = []
    for kw in keywords:
        start = 0
        while (idx := lowered.find(kw, start)) != -1:
            positions.append(idx)
            start = idx + 1
    return positions


def node_init(state: PreSalesState) -> dict[str, Any]:
    """
    PS-01 — Init: khởi tạo phiên tư vấn, thiết lập TTL 1800s và thread identity.
    Invariant: phiên Pre-Sales không bao giờ chạm KMS/Outbox/Official Quote.
    """
    now = datetime.now(UTC)
    return {
        "status": "WAITING_FOR_CUSTOMER_INPUT",
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=SESSION_TTL_SECONDS)).isoformat(),
        "collected_fields": [],
        "policy_conflicts": [],
        "error": None,
        "agent_message": WELCOME_MESSAGE,
        "_interrupt_gate": "WAITING_FOR_CUSTOMER_INPUT",
    }


def node_collect_input(state: PreSalesState) -> dict[str, Any]:
    """
    PS-02 — Input Collector: quét lời nhắn của khách, nhận diện trường ràng buộc
    đã cung cấp. Node chạy sau mỗi lần resume từ interrupt chờ tin nhắn.
    """
    message = state.get("last_customer_message", "") or ""
    collected = list(state.get("collected_fields", []))
    constraints: dict[str, Any] = dict(state.get("customer_constraints") or {})

    lowered = message.lower()
    for field, keywords in FIELD_KEYWORDS:
        if field in collected:
            continue
        if any(kw in lowered for kw in keywords):
            collected.append(field)

    # Map từng số tiền về trường ràng buộc theo từ khóa ĐỨNG TRƯỚC nó gần nhất
    # (quy luật tiếng Việt: 'vốn tự có 1.5 tỷ, trả góp 40 triệu' — giá trị luôn
    # theo sau từ khóa của nó; so sánh hai phía sẽ bị đảo 'trả góp' gần số thứ nhất).
    # Compound ('vốn 2 tỷ 500 triệu') chỉ cộng dồn trong CÙNG một lượt nhắn;
    # nhắc lại số ở lượt khác là cập nhật (ghi đè) chứ không cộng dồn.
    amounts = extract_amounts(message)
    if amounts:
        own_pos = _keyword_positions(lowered, ("vốn", "tự có", "own funds"))
        monthly_pos = _keyword_positions(lowered, ("trả góp", "thu nhập", "hàng tháng", "monthly"))
        own_seen = 0
        mon_seen = 0
        for pos, value in amounts:
            own_cand = max((p for p in own_pos if p < pos), default=None)
            mon_cand = max((p for p in monthly_pos if p < pos), default=None)
            if own_cand is not None and (mon_cand is None or own_cand >= mon_cand):
                own_seen += 1
                constraints["own_funds_vnd"] = (
                    constraints.get("own_funds_vnd", 0) + value if own_seen > 1 else value
                )
            elif mon_cand is not None:
                mon_seen += 1
                constraints["monthly_capacity_vnd"] = (
                    constraints.get("monthly_capacity_vnd", 0) + value if mon_seen > 1 else value
                )
            else:
                # Không có từ khóa nào đứng trước số ('2 tỷ 500 triệu'):
                # nếu lượt này đã nhắc vốn thì cộng dồn, ngược lại gán mới cho vốn.
                if own_seen > 0:
                    constraints["own_funds_vnd"] += value
                else:
                    constraints["own_funds_vnd"] = value
                    own_seen = 1

    # Nhận diện mã căn / dự án dạng chữ
    if "project_id" not in constraints and any(kw in lowered for kw in ("dự án", "project")):
        constraints["project_id"] = message.strip().upper()[:64] if message else None

    next_status = (
        "WAITING_FOR_CUSTOMER_INPUT" if len(collected) < 2 else "ACTIVE"
    )
    return {
        "collected_fields": collected,
        "customer_constraints": constraints or None,
        "status": next_status,
        "_interrupt_gate": None,
        "agent_message": (
            "Cảm ơn anh/chị! Em đã ghi nhận thông tin ban đầu."
            if next_status == "ACTIVE"
            else "Anh/chị cho em thêm thông tin về vốn tự có hoặc khả năng trả góp hàng tháng được không ạ?"
        ),
    }
