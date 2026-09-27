"""
Watermark Reference PDF Worker (C-09 / PS-09).
Owner: Phase 2 — Pre-Sales Advisory StateGraph

Sinh bản ước tính tham khảo PDF tức thời (< 1.5s) với watermark chìm 45 độ:
"BẢN ƯỚC TÍNH THAM KHẢO TIỀN BÁN HÀNG - KHÔNG PHẢI BÁO GIÁ CHÍNH THỨC"

Ranh giới Zero-Trust:
- KHÔNG ký số KMS, KHÔNG mã QR cam kết, KHÔNG ghi transactional_outbox.
- Dùng reportlab nếu có; fallback pure-Python (HTML-in-PDF skeleton) nếu thư viện
  chưa cài — luôn bảo đảm watermark text xuất hiện trong tài liệu đầu ra.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

WATERMARK_TEXT = (
    "BẢN ƯỚC TÍNH THAM KHẢO TIỀN BÁN HÀNG - KHÔNG PHẢI BÁO GIÁ CHÍNH THỨC"
)


def _fmt_vnd(value: int | float | str | None) -> str:
    try:
        return f"{int(value or 0):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "0"


def generate_reference_pdf(
    plan_id: str,
    unit_code: str,
    scenarios: dict[str, dict[str, Any]],
    recommended_code: str,
    watermark_text: str = WATERMARK_TEXT,
    output_dir: str | None = None,
) -> str:
    """
    Sinh PDF tham khảo cho Pre-Sales Plan. Trả về đường dẫn file local.
    Ưu tiên reportlab (PDF thật); nếu thiếu lib, fallback .txt pseudo-PDF
    vẫn chứa watermark + nội dung phương án để test và demo offline.
    """
    output_dir = output_dir or os.path.join("data", "pre_sales_pdfs")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    safe_name = f"presales_plan_{plan_id}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.pdf"
    out_path = os.path.join(output_dir, safe_name)

    try:
        return _render_with_reportlab(
            out_path, plan_id, unit_code, scenarios, recommended_code, watermark_text
        )
    except ImportError:
        # Fallback renderer writes plain text — use .txt extension to avoid confusion
        fallback_path = out_path.replace(".pdf", ".txt")
        return _render_fallback_text(
            fallback_path, plan_id, unit_code, scenarios, recommended_code, watermark_text
        )


# ---------------------------------------------------------------------------
# reportlab renderer (production path)
# ---------------------------------------------------------------------------

def _render_with_reportlab(
    out_path: str,
    plan_id: str,
    unit_code: str,
    scenarios: dict[str, dict[str, Any]],
    recommended_code: str,
    watermark_text: str,
) -> str:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(out_path, pagesize=A4)
    width, height = A4

    # ---- Watermark chìm 45 độ trên mọi trang ----
    c.saveState()
    c.setFont("Helvetica", 40)
    c.setFillAlpha(0.12)  # watermark chìm mờ
    c.translate(width / 2, height / 2)
    c.rotate(45)
    c.drawCentredString(0, 0, watermark_text)
    c.restoreState()

    # ---- Header ----
    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, height - 20 * mm, "BAN UOC TINH THAM KHAO TIEN BAN HANG")
    c.setFont("Helvetica", 10)
    c.drawString(20 * mm, height - 28 * mm, f"Plan: {plan_id}  |  Can: {unit_code}")
    c.drawString(
        20 * mm,
        height - 33 * mm,
        f"Thoi diem lap: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}",
    )

    # ---- Chi tiết từng phương án ----
    y = height - 45 * mm
    for code, sc in scenarios.items():
        if y < 60 * mm:
            c.showPage()
            c.saveState()
            c.setFont("Helvetica", 40)
            c.setFillAlpha(0.12)
            c.translate(width / 2, height / 2)
            c.rotate(45)
            c.drawCentredString(0, 0, watermark_text)
            c.restoreState()
            y = height - 30 * mm

        marker = "[DE XUAT] " if code == recommended_code else ""
        c.setFont("Helvetica-Bold", 12)
        c.drawString(20 * mm, y, f"{marker}{sc.get('scenario_name', code)}")
        y -= 7 * mm
        c.setFont("Helvetica", 9)
        rows = [
            ("Gia net (chua VAT)", sc.get("net_price_vnd")),
            ("VAT 10%", sc.get("vat_vnd")),
            ("KPBT 2%", sc.get("kpbt_vnd")),
            ("Tong gia tri hop dong", sc.get("total_contract_price_vnd")),
            ("Tien mat dot 1", sc.get("initial_cash_outflow_vnd")),
            ("Tra hang thang BQ", sc.get("monthly_burden_vnd")),
        ]
        for label, value in rows:
            c.drawString(22 * mm, y, f"{label}: {_fmt_vnd(value)} VNĐ")
            y -= 5.5 * mm
        y -= 4 * mm

    # ---- Footer disclaimer ----
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(
        20 * mm,
        15 * mm,
        "Phuong an chi mang tinh chat tham khao, khong cau thanh cam ket bao gia chinh thuc.",
    )
    c.save()
    return out_path


# ---------------------------------------------------------------------------
# Fallback renderer (không cần reportlab — dùng cho môi trường dev/CI gọn)
# ---------------------------------------------------------------------------

def _render_fallback_text(
    out_path: str,
    plan_id: str,
    unit_code: str,
    scenarios: dict[str, dict[str, Any]],
    recommended_code: str,
    watermark_text: str,
) -> str:
    """Fallback: ghi pseudo-PDF dạng text chứa watermark — bảo đảm verify được."""
    lines = [
        watermark_text,
        "=" * 72,
        f"Plan: {plan_id}",
        f"Can: {unit_code}",
        f"Thoi diem lap: {datetime.now(UTC).isoformat()}",
        "",
    ]
    for code, sc in scenarios.items():
        marker = "[DE XUAT] " if code == recommended_code else ""
        lines.append(f"{marker}{sc.get('scenario_name', code)}")
        lines.append(
            f"  Tong gia tri hop dong: {_fmt_vnd(sc.get('total_contract_price_vnd'))} VND"
        )
        lines.append(f"  Tien mat dot 1: {_fmt_vnd(sc.get('initial_cash_outflow_vnd'))} VND")
        lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out_path
