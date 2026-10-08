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

Chốt P1.5 (cập nhật): **mọi danh sách căn đều trình bày dạng bảng** — kể cả 1–2 căn — để Sale nhìn
theo cột cho nhanh, không còn kiểu liệt kê dòng.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.agents.copilot import grounding

#: Cột **cơ bản** — hiện trên mọi khổ màn hình (chốt R19: `Dự án` và `Phòng ngủ` bắt buộc có mặt).
TABLE_HEADERS = ("Mã căn", "Dự án", "Phòng ngủ", "Diện tích", "Giá niêm yết (trước thuế)")

#: Cột **mở rộng** — chỉ hiện ở màn hình rộng (PC ≥ 1280px). Giao diện nhận biết bằng dấu `*` ở cuối
#: tiêu đề (xem `WIDE_COLUMN_MARK`) và ẩn cột đó ở màn hình nhỏ. Cột hẹp trên mobile nhờ vậy không bị bóp.
#: Cột mở rộng thứ hai là **View** — đúng tên trường dữ liệu (`units.view`; dữ liệu canonical cũng dùng
#: `view`), theo chốt đợt 20. Không gọi là "hướng" vì đây là hướng nhìn, không phải hướng ban công.
TABLE_HEADERS_WIDE = ("Tầng", "View")

#: Dấu đánh vào tiêu đề cột mở rộng — lớp hiển thị bóc dấu này trước khi in ra.
WIDE_COLUMN_MARK = "*"

#: Ô không có dữ liệu: in gạch dài thay vì số 0 hay số suy diễn (DB vận hành chưa lưu diện tích/hướng).
EMPTY_CELL = "—"


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
        f"({area_text(unit.get('area_m2'))}, {grounding.project_name(unit.get('project_id'))}) với giá "
        f"{grounding.format_vnd(unit.get('listed_price_before_tax_vnd'))}"
    )
    if stats.gap_vnd:
        line += f" — cao hơn ngân sách dự kiến {grounding.format_vnd(stats.gap_vnd)}"
    return line + "."


def next_steps(bedrooms: int, budget_vnd: int | None = None) -> list[str]:
    """Hai hướng đi tiếp khi lọc rỗng (chốt P1.1) — câu hỏi điều hướng, không tự đổi nhu cầu khách.

    Sale có thể không nêu số phòng ngủ (chỉ nêu diện tích/ngân sách) — khi đó KHÔNG được nói "giữ
    nguyên 0PN" (vô nghĩa với người đọc, lỗi đã gặp ở đợt 25): dùng tiêu chí hiện tại làm mốc.
    """
    lower = max(1, bedrooms - 1)
    budget_text = f"ngân sách {grounding.format_vnd(budget_vnd)}" if budget_vnd else "ngân sách hiện tại"
    if not bedrooms:
        return [
            "Giữ nguyên tiêu chí hiện tại (diện tích/ngân sách) và xem phương án vốn tự có/vay cho căn gần nhất.",
            f"Mở rộng khoảng diện tích hoặc nới {budget_text} nếu khách linh hoạt.",
        ]
    return [
        f"Giữ nguyên {bedrooms}PN và xem phương án vốn tự có/vay cho căn mềm nhất.",
        f"Mở rộng sang {lower}PN+1 nếu khách linh hoạt về số phòng ngủ (giữ {budget_text}).",
    ]


def area_text(value: Any) -> str:
    """Diện tích dạng `98.2m²`; DB không lưu diện tích ⇒ `—` (không suy diễn theo loại căn)."""
    try:
        area = float(value)
    except (TypeError, ValueError):
        return EMPTY_CELL
    if area <= 0:
        return EMPTY_CELL
    text = f"{area:.2f}".rstrip("0").rstrip(".")
    return f"{text}m²"


def table_row(unit: dict[str, Any]) -> str:
    """Một dòng bảng: đúng thứ tự và đúng số cột của `TABLE_HEADERS` + `TABLE_HEADERS_WIDE`."""
    bedrooms_raw = unit.get("bedrooms")
    if bedrooms_raw is None:
        bedrooms_text = EMPTY_CELL
    elif int(bedrooms_raw) == 0:
        bedrooms_text = "Studio"
    else:
        bedrooms_text = f"{int(bedrooms_raw)}PN"
    floor = unit.get("floor")
    view = str(unit.get("view") or "").strip()
    project = grounding.project_name(unit.get("project_id")) or EMPTY_CELL
    cells = [
        str(unit.get("unit_code") or EMPTY_CELL),
        project,
        bedrooms_text,
        area_text(unit.get("area_m2")),
        grounding.format_vnd(unit.get("listed_price_before_tax_vnd")),
        f"Tầng {floor}" if floor else EMPTY_CELL,
        view or EMPTY_CELL,
    ]
    return "| " + " | ".join(cells) + " |"


def units_table(units: list[dict[str, Any]]) -> str:
    """Bảng markdown giỏ hàng — **máy dựng**, không để LLM tự viết lại (chống lệch cột/mất cột).

    Cột cơ bản: Mã căn · Dự án · Phòng ngủ · Diện tích · Giá niêm yết (trước thuế).
    Cột mở rộng (PC rộng): Tầng · View — tiêu đề mang dấu `*`, lớp hiển thị ẩn ở màn hình nhỏ.
    """
    if not units:
        return ""
    headers = list(TABLE_HEADERS) + [f"{h}{WIDE_COLUMN_MARK}" for h in TABLE_HEADERS_WIDE]
    header = "| " + " | ".join(headers) + " |"
    divider = "|" + "|".join(["---"] * len(headers)) + "|"
    return "\n".join([header, divider, *(table_row(u) for u in units)])


def render_matches(units: list[dict[str, Any]]) -> str:
    """Có căn cần liệt kê ⇒ luôn trình bày dạng bảng (chốt P1.5, kể cả 1–2 căn)."""
    if not units:
        return ""
    return units_table(units)


def area_range_text(min_m2: float | None, max_m2: float | None, spec_m2: float | None = None) -> str:
    """Nhãn khoảng diện tích đang lọc: `63–77m² (quanh 70m² khách nêu)`.

    Nói rõ khoảng ra để Sale biết vì sao căn 52m² không xuất hiện, thay vì tưởng hệ thống trả thiếu.
    """
    if not min_m2 and not max_m2:
        return ""
    if min_m2 and max_m2:
        label = f"{round(float(min_m2)):g}–{round(float(max_m2)):g}m²"
    elif min_m2:
        label = f"từ {round(float(min_m2)):g}m²"
    else:
        label = f"đến {round(float(max_m2)):g}m²"
    if spec_m2:
        label += f" (quanh {round(float(spec_m2), 1):g}m² khách nêu)"
    return label


def nearest_area_unit(bedrooms: int, target_m2: float, project_id: str | None = None) -> dict[str, Any] | None:
    """Căn có diện tích gần mốc Sale nêu nhất — dùng khi lọc theo diện tích ra rỗng."""
    units = [
        unit
        for unit in grounding.search_units(bedrooms=bedrooms or None, project_id=project_id)
        if unit.get("area_m2")
    ]
    if not units:
        return None
    return min(units, key=lambda u: abs(float(u["area_m2"]) - float(target_m2)))


def nearest_area_line(bedrooms: int, target_m2: float, project_id: str | None = None) -> str:
    """Câu "căn gần khoảng diện tích này nhất" — lọc rỗng vì diện tích vẫn phải có hướng đi tiếp."""
    nearest = nearest_area_unit(bedrooms, target_m2, project_id)
    if not nearest:
        return ""
    return (
        f"Căn gần khoảng diện tích này nhất: căn {nearest.get('unit_code')} "
        f"({area_text(nearest.get('area_m2'))}, {grounding.project_name(nearest.get('project_id'))}) — "
        f"giá niêm yết {grounding.format_vnd(nearest.get('listed_price_before_tax_vnd'))}."
    )


def softest_overall_line() -> str:
    """Căn giá mềm nhất của TOÀN giỏ — mốc so sánh khi Sale chưa nêu số phòng ngủ."""
    stats = segment_stats(0)
    if not stats.softest_unit:
        return ""
    unit = stats.softest_unit
    return (
        f"Căn giá mềm nhất toàn giỏ: căn {unit.get('unit_code')} "
        f"({area_text(unit.get('area_m2'))}, {grounding.project_name(unit.get('project_id'))}) với giá "
        f"{grounding.format_vnd(unit.get('listed_price_before_tax_vnd'))}."
    )


def render_empty_funnel(
    *,
    bedrooms: int,
    budget_vnd: int | None,
    project_id: str | None = None,
    ma_can: str = "",
    area_min_m2: float | None = None,
    area_max_m2: float | None = None,
    area_spec_m2: float | None = None,
    unknown_area_count: int = 0,
) -> str:
    """Observation đầy đủ khi lọc rỗng: thống kê phân khúc + căn mềm nhất + hai hướng đi tiếp."""
    stats = segment_stats(bedrooms, budget_vnd, project_id)
    histogram = bedroom_histogram(project_id)
    total = sum(histogram.values())

    # Giỏ RỖNG HOÀN TOÀN (CSDL vận hành chưa có căn nào): đây không phải "hết căn khớp tiêu chí" mà là
    # **chưa có dữ liệu để đối chiếu**. Phải nói thẳng như vậy — bản cũ in "Toàn giỏ đang mở bán có 0 căn
    # ()" kèm gợi ý "nới ngân sách/chọn căn gần nhất", vô nghĩa và dễ khiến Sale tưởng hệ thống lỗi.
    if total == 0:
        lines = ["Giỏ hàng hiện chưa có căn nào trong dữ liệu vận hành nên em chưa có căn nào để đối chiếu."]
        criteria: list[str] = []
        if budget_vnd:
            criteria.append(f"ngân sách tối đa {grounding.format_vnd(budget_vnd)}")
        area_label_empty = area_range_text(area_min_m2, area_max_m2, area_spec_m2)
        if area_label_empty:
            criteria.append(f"diện tích {area_label_empty}")
        if bedrooms:
            criteria.append(f"{bedrooms} phòng ngủ")
        if criteria:
            lines.append("Tiêu chí anh/chị vừa nêu: " + "; ".join(criteria) + ".")
        lines.append(
            "Anh/chị kiểm tra lại giỏ hàng đã nạp vào CSDL giúp em, hoặc cho em mã căn/dự án cụ thể để em tra."
        )
        return "\n".join(lines)

    lines = ["Không có căn nào khớp đúng tiêu chí lọc."]
    if ma_can.strip():
        lines.append(f"Mã căn '{ma_can.strip()}' không có trong giỏ hàng đang mở bán.")
    if project_id:
        lines.append(f"Đã lọc theo dự án {grounding.project_name(project_id)}.")
    if budget_vnd:
        lines.append(f"Tiêu chí ngân sách: tối đa {grounding.format_vnd(budget_vnd)} (giá niêm yết trước thuế).")
    area_label = area_range_text(area_min_m2, area_max_m2, area_spec_m2)
    if area_label:
        lines.append(f"Tiêu chí diện tích: {area_label}.")
        if unknown_area_count:
            lines.append(
                f"{unknown_area_count} căn đang mở bán chưa có dữ liệu diện tích nên chưa đối chiếu được."
            )

    if stats.count and bedrooms:
        lines.append(segment_summary_line(stats))
        lines.append(softest_unit_line(stats))
    elif not bedrooms:
        # Sale chỉ nêu diện tích/ngân sách, không nêu số phòng ngủ ⇒ KHÔNG có "phân khúc" nào để nói;
        # mốc so sánh đúng là toàn giỏ (tránh câu vô nghĩa "phân khúc 0PN").
        lines.append(softest_overall_line())
    else:
        lines.append(f"Phân khúc {bedrooms}PN hiện không còn căn nào đang mở bán.")

    if area_label:
        target = (float(area_min_m2 or 0) + float(area_max_m2 or 0)) / 2 or float(area_spec_m2 or 0)
        nearest = nearest_area_line(bedrooms, target, project_id)
        if nearest:
            lines.append(nearest)

    spread = ", ".join(f"{bedrooms_}PN: {count} căn" for bedrooms_, count in histogram.items())
    lines.append(f"Toàn giỏ đang mở bán có {total} căn ({spread}) — đây là số liệu của TOÀN GIỎ.")
    lines.extend(f"Hướng tiếp theo: {step}" for step in next_steps(bedrooms, budget_vnd))
    return "\n".join(lines)


__all__ = [
    "EMPTY_CELL",
    "TABLE_HEADERS",
    "TABLE_HEADERS_WIDE",
    "WIDE_COLUMN_MARK",
    "SegmentStats",
    "area_range_text",
    "area_text",
    "bedroom_histogram",
    "nearest_area_line",
    "nearest_area_unit",
    "next_steps",
    "render_empty_funnel",
    "softest_overall_line",
    "render_matches",
    "table_row",
    "segment_stats",
    "segment_summary_line",
    "softest_unit_line",
    "units_table",
]
