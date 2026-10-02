"""Phễu dữ liệu giỏ hàng cho câu hỏi "có căn nào khớp tiêu chí không?" (P1.1 · P1.3 · P1.5).

Vì sao cần module riêng: `tra_cuu_gio_hang` bản cũ khi lọc rỗng chỉ trả đúng một câu
"Không còn căn nào phù hợp tiêu chí" ⇒ **mất toàn bộ thông tin phễu**. LLM không còn số liệu nào để
giải thích, buộc phải nhớ lại bối cảnh prompt (dải giá toàn giỏ) và dễ ghép sai nhãn phân khúc
("4 căn" của toàn giỏ thành "4 căn 3 ngủ").

Ở đây mọi con số đều được tính tất định từ dữ liệu canonical và **ghi vào Observation**, nên:
- LLM chỉ diễn đạt lại, không tự bịa;
- verifier đối chiếu được;
- câu trả lời luôn có "bước tiếp theo" thay vì ngõ cụt.

Nội dung phễu (theo chốt thiết kế P1.1/P1.3):
- thống kê phân khúc theo số phòng ngủ: số căn, giá thấp nhất → cao nhất;
- căn **mềm nhất** của phân khúc + **chênh lệch** so với ngân sách Sale nêu;
- hai hướng đi tiếp: giữ ngân sách → lọc xuống 2PN+1; giữ 3PN → xem phương án vốn tự có/vay.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.agents.copilot import grounding

#: Số căn tối thiểu để chuyển từ liệt kê dòng sang bảng rút gọn (chốt P1.5: từ 3 căn).
TABLE_THRESHOLD = 3

#: Cột bảng rút gọn theo chốt P1.5.
TABLE_HEADERS = ("Căn", "Dự án", "Số PN", "Diện tích", "Giá niêm yết")


@dataclass
class SegmentStats:
    """Thống kê một phân khúc (theo số phòng ngủ) trong giỏ đang mở bán."""

    bedrooms: int
    count: int
    min_price: int | None = None
    max_price: int | None = None
    softest_unit: dict[str, Any] | None = None
    #: Chênh lệch giữa giá căn mềm nhất và ngân sách Sale nêu (0 nếu không nêu ngân sách).
    gap_vnd: int | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "bedrooms": self.bedrooms,
            "count": self.count,
            "price_min_vnd": self.min_price,
            "price_max_vnd": self.max_price,
        }
        if self.softest_unit:
            payload["softest_unit_code"] = self.softest_unit.get("unit_code")
            payload["softest_unit_price_vnd"] = self.softest_unit.get("listed_price_before_tax_vnd")
        if self.gap_vnd is not None:
            payload["gap_vs_budget_vnd"] = self.gap_vnd
        return payload


def bedroom_histogram(project_id: str | None = None) -> dict[int, int]:
    """Số căn đang mở bán theo từng số phòng ngủ — nguồn chính danh cho câu "giỏ có N căn XPN"."""
    histogram: dict[int, int] = {}
    for unit in grounding.search_units(project_id=project_id):
        bedrooms = int(unit.get("bedrooms") or 0)
        histogram[bedrooms] = histogram.get(bedrooms, 0) + 1
    return dict(sorted(histogram.items()))


def segment_stats(bedrooms: int, budget_vnd: int | None = None, project_id: str | None = None) -> SegmentStats:
    """Thống kê phân khúc `bedrooms` PN; `gap_vnd` tính theo căn **mềm nhất** (P1.3)."""
    units = grounding.search_units(bedrooms=bedrooms or None, project_id=project_id)
    if not units:
        return SegmentStats(bedrooms=bedrooms, count=0)
    prices = [int(u.get("listed_price_before_tax_vnd") or 0) for u in units]
    softest = units[0]  # search_units đã sắp giá tăng dần
    gap = None
    if budget_vnd:
        gap = max(0, int(softest.get("listed_price_before_tax_vnd") or 0) - int(budget_vnd))
    return SegmentStats(
        bedrooms=bedrooms,
        count=len(units),
        min_price=min(prices),
        max_price=max(prices),
        softest_unit=softest,
        gap_vnd=gap,
    )


def segment_summary_line(stats: SegmentStats, *, prefix: str = "") -> str:
    """Một dòng mô tả phân khúc, luôn kèm nhãn số phòng ngủ để không lẫn với toàn giỏ."""
    if not stats.count or stats.min_price is None or stats.max_price is None:
        return f"{prefix}Phân khúc {stats.bedrooms}PN hiện không còn căn nào đang mở bán."
    return (
        f"{prefix}Phân khúc **{stats.bedrooms}PN** hiện có {stats.count} căn đang mở bán, "
        f"giá niêm yết trước thuế từ {grounding.format_vnd(stats.min_price)} đến "
        f"{grounding.format_vnd(stats.max_price)}."
    )


def softest_unit_line(stats: SegmentStats) -> str:
    """Dòng "căn mềm nhất + chênh lệch" theo chốt P1.3 — báo mềm nhất, không dội căn đắt nhất."""
    if not stats.softest_unit:
        return ""
    unit = stats.softest_unit
    line = (
        f"Căn {stats.bedrooms}PN giá mềm nhất hiện tại là căn {unit.get('unit_code')} "
        f"({unit.get('area_m2')}m², {grounding.project_name(unit.get('project_id'))}) với giá "
        f"{grounding.format_vnd(unit.get('listed_price_before_tax_vnd'))}"
    )
    if stats.gap_vnd:
        line += f" — cao hơn ngân sách dự kiến {grounding.format_vnd(stats.gap_vnd)}"
    return line + "."


def next_steps(bedrooms: int, budget_vnd: int | None = None) -> list[str]:
    """Hai hướng đi tiếp khi lọc rỗng (chốt P1.1) — câu hỏi điều hướng, không tự đổi nhu cầu khách."""
    lower = max(1, bedrooms - 1)
    budget_text = f"ngân sách {grounding.format_vnd(budget_vnd)}" if budget_vnd else "ngân sách hiện tại"
    return [
        f"Giữ nguyên {bedrooms}PN và xem phương án vốn tự có/vay cho căn mềm nhất.",
        f"Mở rộng sang {lower}PN+1 nếu khách linh hoạt về số phòng ngủ (giữ {budget_text}).",
    ]


def units_table(units: list[dict[str, Any]]) -> str:
    """Bảng markdown rút gọn theo chốt P1.5 (Căn, Dự án, Số PN, Diện tích, Giá niêm yết)."""
    if not units:
        return ""
    header = "| " + " | ".join(TABLE_HEADERS) + " |"
    divider = "|" + "|".join(["---"] * len(TABLE_HEADERS)) + "|"
    rows = [
        "| {code} | {project} | {bedrooms} | {area}m² | {price} |".format(
            code=u.get("unit_code"),
            project=grounding.project_name(u.get("project_id")),
            bedrooms=u.get("bedrooms"),
            area=u.get("area_m2"),
            price=grounding.format_vnd(u.get("listed_price_before_tax_vnd")),
        )
        for u in units
    ]
    return "\n".join([header, divider, *rows])


def render_matches(units: list[dict[str, Any]]) -> str:
    """Dưới 3 căn → liệt kê dòng; từ 3 căn → bảng rút gọn (chốt P1.5)."""
    if not units:
        return ""
    if len(units) < TABLE_THRESHOLD:
        lines = []
        for u in units:
            lines.append(
                f"- {u.get('unit_code')} · {u.get('bedrooms')}PN · {u.get('area_m2')}m² · "
                f"{grounding.format_vnd(u.get('listed_price_before_tax_vnd'))} · {u.get('status')}"
            )
        return "\n".join(lines)
    return units_table(units)


def render_empty_funnel(
    *,
    bedrooms: int,
    budget_vnd: int | None,
    project_id: str | None = None,
    ma_can: str = "",
) -> str:
    """Observation đầy đủ khi lọc rỗng: thống kê phân khúc + căn mềm nhất + hai hướng đi tiếp."""
    stats = segment_stats(bedrooms, budget_vnd, project_id)
    histogram = bedroom_histogram(project_id)
    total = sum(histogram.values())

    lines = ["Không có căn nào khớp đúng tiêu chí lọc."]
    if ma_can.strip():
        lines.append(f"Mã căn '{ma_can.strip()}' không có trong giỏ canonical.")
    if project_id:
        lines.append(f"Đã lọc theo dự án {grounding.project_name(project_id)}.")
    if budget_vnd:
        lines.append(f"Tiêu chí ngân sách: tối đa {grounding.format_vnd(budget_vnd)} (giá niêm yết trước thuế).")

    if stats.count:
        lines.append(segment_summary_line(stats))
        lines.append(softest_unit_line(stats))
    else:
        lines.append(f"Phân khúc {bedrooms}PN hiện không còn căn nào đang mở bán.")

    spread = ", ".join(f"{bedrooms_}PN: {count} căn" for bedrooms_, count in histogram.items())
    lines.append(f"Toàn giỏ đang mở bán có {total} căn ({spread}) — đây là số liệu của TOÀN GIỎ.")
    lines.extend(f"Hướng tiếp theo: {step}" for step in next_steps(bedrooms, budget_vnd))
    return "\n".join(lines)


__all__ = [
    "TABLE_HEADERS",
    "TABLE_THRESHOLD",
    "SegmentStats",
    "bedroom_histogram",
    "next_steps",
    "render_empty_funnel",
    "render_matches",
    "segment_stats",
    "segment_summary_line",
    "softest_unit_line",
    "units_table",
]
