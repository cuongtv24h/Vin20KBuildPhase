"""Tool catalog cho Sales Copilot ReAct Agent.

Mỗi tool trả về JSON string (ensure_ascii=False) với 2 phần:
- `summary`: quan sát dạng người đọc (Observation cho LLM & hiển thị UI)
- `citations`: căn cứ pháp lý/số liệu (policy_id · điều khoản · trích dẫn · hash)

Nguyên tắc Zero-Trust: tool chỉ ĐỌC dữ liệu canonical hoặc gọi engine tất định.
Không tool nào tự ghi DB / tự duyệt / tự gửi tin — mọi hành động ghi vẫn do người
dùng bấm xác nhận ở Smart Card phía UI.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, date, datetime
from typing import Any

from langchain_core.tools import tool

from src.agents.copilot import grounding, inventory_funnel
from src.contracts.enums import OptimizationObjective
from src.services.compliance.gate import ComplianceCheckRequest, ComplianceGate

logger = logging.getLogger(__name__)

MAX_OBSERVATION_CHARS = 1_800


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _now_iso() -> str:
    """Mốc thời gian đọc dữ liệu (P1.6) — dùng cho watermark ở UI, không đưa vào câu trả lời."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def _clip(text: str, limit: int = MAX_OBSERVATION_CHARS) -> str:
    return text if len(text) <= limit else text[:limit] + " …(đã lược bớt)"


def _objective_from_text(value: str | None) -> OptimizationObjective:
    if not value:
        return OptimizationObjective.MIN_INITIAL_CASH
    raw = str(value).strip()
    try:
        return OptimizationObjective(raw)
    except ValueError:
        pass
    key = grounding.normalize(raw)
    mapping = [
        ("chi phi ban dau", OptimizationObjective.MIN_INITIAL_CASH),
        ("it von", OptimizationObjective.MIN_INITIAL_CASH),
        ("gia net", OptimizationObjective.MIN_NET_PRICE),
        ("gia thap", OptimizationObjective.MIN_NET_PRICE),
        ("gia hop dong", OptimizationObjective.MIN_CONTRACT_PRICE),
        ("dong tien", OptimizationObjective.MIN_TOTAL_CASH_OUTFLOW),
        ("qua tang", OptimizationObjective.MAX_BENEFIT_VALUE),
    ]
    for token, objective in mapping:
        if token in key:
            return objective
    return OptimizationObjective.MIN_INITIAL_CASH


# ---------------------------------------------------------------------------
# Tool 1 — Tra cứu chính sách (PEC-RAG time-travel + fallback canonical)
# ---------------------------------------------------------------------------
@tool
async def tra_cuu_chinh_sach(cau_hoi: str, ngay_hieu_luc: str = "", du_an: str = "") -> str:
    """Tra cứu điều khoản chính sách bán hàng có hiệu lực tại một ngày (time-travel).

    Args:
        cau_hoi: Câu hỏi/từ khóa nghiệp vụ, ví dụ "chiết khấu thanh toán sớm 95%".
        ngay_hieu_luc: Ngày giao dịch YYYY-MM-DD (mặc định hôm nay).
        du_an: Mã dự án (THE_ZEN_PARK / VLANDFUTURE_SAPPHIRE), để trống nếu chưa rõ.
    """
    try:
        tx_date = date.fromisoformat(ngay_hieu_luc.strip()) if ngay_hieu_luc.strip() else date.today()
    except ValueError:
        tx_date = date.today()

    project_id = du_an.strip() or None

    # 1) Ưu tiên PEC-RAG thật (pgvector / DB đã seed)
    clauses: list[dict[str, Any]] = []
    try:
        from src.agents.tools.policy_search import get_rag_service

        service = get_rag_service()
        for clause in service.retrieve(query=cau_hoi, as_of_date=tx_date, top_k=5):
            clauses.append(
                {
                    "policy_id": clause.policy_id,
                    "section": " ".join(x for x in [clause.article, clause.clause] if x),
                    "quote": clause.text.strip(),
                    "valid_from": str(clause.valid_from),
                    "valid_to": str(clause.valid_to),
                    "score": round(float(clause.score or 0.0), 3),
                    "source": "PEC_RAG",
                }
            )
    except Exception as exc:  # pragma: no cover — phụ thuộc môi trường seed
        logger.info("PEC-RAG chưa sẵn sàng cho Copilot (%s) — dùng fixture canonical.", exc)

    citations: list[dict[str, Any]] = []
    if clauses:
        citations = [
            {
                "policy_id": c["policy_id"],
                "section": c["section"],
                "quote": c["quote"],
                "effective_from": c["valid_from"],
                "effective_to": c["valid_to"],
                "score": c["score"],
                "source": c["source"],
            }
            for c in clauses
        ]
        lines = [f"Tìm thấy {len(clauses)} điều khoản có hiệu lực tại {tx_date.isoformat()}:"]
        for idx, c in enumerate(clauses, 1):
            lines.append(f"{idx}. [{c['policy_id']} · {c['section']}] (score {c['score']})\n   {c['quote']}")
        summary = _clip("\n".join(lines))
    else:
        # 2) Fallback fixture canonical (demo offline, SQLite chưa seed)
        policy = grounding.resolve_active_policy(project_id, tx_date)
        hits = grounding.find_rules_by_keyword(cau_hoi, project_id)
        if not hits and policy:
            hits = [(policy, rule) for rule in policy.get("rules", []) if rule.get("is_selectable")]
        # Giữ tối đa 4 rule sát nhất
        hits = hits[:4]
        if not hits:
            summary = (
                f"Không tìm thấy điều khoản nào khớp '{cau_hoi}' trong chính sách hiệu lực "
                f"tại {tx_date.isoformat()}. Đề nghị nói rõ chính sách cần tra."
            )
        else:
            lines = [
                f"Chính sách canonical đang hiệu lực tại {tx_date.isoformat()} "
                f"({grounding.project_name(policy.get('project_id') if policy else project_id)}):"
            ]
            for pol, rule in hits:
                src = rule.get("source") or {}
                lines.append(
                    f"- [{pol['policy_id']} · {src.get('section', rule.get('rule_code'))}] {rule.get('title')}"
                    f"\n  Trích dẫn: \"{src.get('quote', '')}\""
                )
            summary = _clip("\n".join(lines))
            citations = grounding.policy_citations(policy, [rule for _, rule in hits]) if policy else []

    return _dump(
        {
            "tool": "tra_cuu_chinh_sach",
            "as_of_date": tx_date.isoformat(),
            "summary": summary,
            "citations": citations,
        }
    )


# ---------------------------------------------------------------------------
# Tool 2 — Tra cứu giỏ hàng
# ---------------------------------------------------------------------------
@tool
def tra_cuu_gio_hang(so_phong_ngu: int = 0, gia_toi_da_vnd: int = 0, ma_can: str = "", du_an: str = "") -> str:
    """Tra cứu giỏ hàng căn hộ đang mở bán (theo mã căn, số phòng ngủ, ngân sách, dự án).

    Args:
        so_phong_ngu: Số phòng ngủ cần lọc (0 = bỏ qua).
        gia_toi_da_vnd: Giá niêm yết tối đa trước thuế (0 = bỏ qua).
        ma_can: Mã căn cụ thể cần xem chi tiết (để trống nếu tìm theo tiêu chí).
        du_an: Mã dự án cần lọc.
    """
    if ma_can.strip():
        unit = grounding.find_unit(ma_can.strip())
        if not unit:
            return _dump(
                {
                    "tool": "tra_cuu_gio_hang",
                    "summary": f"Không có căn '{ma_can}' trong giỏ hàng canonical.",
                    "citations": [],
                    "data_as_of": _now_iso(),
                }
            )
        summary = (
            f"Căn {unit['unit_code']} — {grounding.project_name(unit.get('project_id'))}: "
            f"{unit.get('bedrooms')}PN, {unit.get('area_m2')}m², {unit.get('view')}, "
            f"giá niêm yết trước thuế {grounding.format_vnd(unit.get('listed_price_before_tax_vnd'))}, "
            f"trạng thái {unit.get('status')}."
        )
        entries = [unit]
    else:
        entries = grounding.search_units(
            bedrooms=so_phong_ngu or None,
            max_price_vnd=gia_toi_da_vnd or None,
            project_id=du_an.strip() or None,
        )[:8]

    citations = [
        {
            "policy_id": "CATALOG-UNITS",
            "section": f"Căn {u['unit_code']}",
            "quote": (
                f"{u.get('bedrooms')}PN · {u.get('area_m2')}m² · "
                f"{grounding.format_vnd(u.get('listed_price_before_tax_vnd'))} · {u.get('status')}"
            ),
            "source": "CANONICAL_CATALOG",
        }
        for u in entries
    ]

    if not entries:
        # Lọc rỗng **không** phải ngõ cụt: trả về phễu dữ liệu (phân khúc, căn mềm nhất, chênh lệch,
        # hai hướng đi tiếp) để câu trả lời có số liệu thật thay vì một câu "không có" trống rỗng.
        summary = _clip(
            inventory_funnel.render_empty_funnel(
                bedrooms=int(so_phong_ngu or 0),
                budget_vnd=int(gia_toi_da_vnd or 0) or None,
                project_id=du_an.strip() or None,
                ma_can=ma_can,
            )
        )
    else:
        scope_label = f"riêng phân khúc {int(so_phong_ngu)}PN" if so_phong_ngu else "toàn giỏ đang mở bán"
        header = f"{len(entries)} căn phù hợp tiêu chí trong {scope_label} (giá chưa gồm VAT):"
        summary = _clip("\n".join([header, inventory_funnel.render_matches(entries)]))

    return _dump(
        {
            "tool": "tra_cuu_gio_hang",
            "summary": summary,
            "citations": citations,
            # Mốc thời gian của **dữ liệu** — UI hiển thị dạng watermark, KHÔNG đưa vào văn phong
            # câu trả lời để Sale copy gửi khách được nguyên văn (chốt P1.6).
            "data_as_of": _now_iso(),
            # Nguồn chính danh cho mọi câu "giỏ có N căn XPN" — chống lỗi ghép nhãn phân khúc (P3.2).
            "bedroom_histogram": {str(k): v for k, v in inventory_funnel.bedroom_histogram(du_an.strip() or None).items()},
            # Máy đọc được: phễu này khớp được bao nhiêu căn và đang lọc theo tiêu chí nào.
            "match_count": len(entries),
            # Cổng CI (chốt P3.2): lọc 3PN thì MỌI căn trả về phải là 3PN. Trộn phân khúc trong bán
            # bất động sản là lỗi cấm — kiểm bằng máy ngay tại nguồn, không đọc bằng mắt.
            "segment_check": {
                "requested_bedrooms": int(so_phong_ngu or 0) or None,
                "returned_bedrooms": sorted({int(u.get("bedrooms") or 0) for u in entries}),
                "ok": (
                    not so_phong_ngu
                    or all(int(u.get("bedrooms") or 0) == int(so_phong_ngu) for u in entries)
                ),
            },
            "scope": {
                "bedrooms": int(so_phong_ngu or 0) or None,
                "budget_vnd": int(gia_toi_da_vnd or 0) or None,
                "project_id": du_an.strip() or None,
            },
        }
    )


# ---------------------------------------------------------------------------
# Tool 3 — Tính 3 phương án thanh toán (Deterministic Engine)
# ---------------------------------------------------------------------------
@tool
async def tinh_phuong_an_thanh_toan(
    ma_can: str,
    von_tu_co_vnd: int = 0,
    kha_nang_thang_vnd: int = 0,
    muc_tieu: str = "",
    ngay_giao_dich: str = "",
) -> str:
    """Tính 3 phương án thanh toán tất định (PA-CHUDONG / PA-NHANH / PA-VAY) cho một căn.

    Dùng engine tài chính Decimal (FCS v2.6) — không để LLM tự tính tiền.

    Args:
        ma_can: Mã căn hộ, ví dụ ZEN-A-1205.
        von_tu_co_vnd: Vốn tự có của khách (VNĐ).
        kha_nang_thang_vnd: Khả năng chi trả hàng tháng (VNĐ).
        muc_tieu: Mục tiêu tối ưu (MIN_INITIAL_CASH, MIN_NET_PRICE, MIN_CONTRACT_PRICE,
            MIN_TOTAL_CASH_OUTFLOW, MAX_BENEFIT_VALUE).
        ngay_giao_dich: Ngày giao dịch YYYY-MM-DD (mặc định hôm nay).
    """
    from src.contracts.pricing import PricingInput
    from src.services.pricing.client import PricingClient

    unit = grounding.find_unit(ma_can)
    if not unit:
        return _dump(
            {
                "tool": "tinh_phuong_an_thanh_toan",
                "error": f"Không tìm thấy căn '{ma_can}' trong giỏ hàng để tính.",
                "summary": f"Không tìm thấy căn '{ma_can}' nên chưa thể tính phương án.",
                "citations": [],
            }
        )

    tx_date = ngay_giao_dich.strip() or date.today().isoformat()
    objective = _objective_from_text(muc_tieu)

    pricing_input = PricingInput(
        project_id=str(unit.get("project_id")),
        unit_code=str(unit.get("unit_code")),
        listed_price_before_tax_vnd=int(unit.get("listed_price_before_tax_vnd", 0)),
        transaction_date=tx_date,
        own_funds_vnd=int(von_tu_co_vnd or 0),
        monthly_capacity_vnd=int(kha_nang_thang_vnd or 0),
        objective=objective,
        execution_context="SALES_COPILOT",
    )

    # In-process deterministic engine (Decimal 28) là nguồn chân lý; sidecar chỉ là tối ưu IPC.
    force_mock = os.environ.get("COPILOT_PRICING_VIA_SIDECAR", "false").lower() not in ("true", "1")
    client = PricingClient(force_mock=force_mock)
    result = await client.calculate(pricing_input)

    policy = grounding.resolve_active_policy(str(unit.get("project_id")), date.fromisoformat(tx_date))
    lines = [
        f"Kết quả engine tất định cho {unit['unit_code']} (objective {objective.value}, ngày {tx_date}):",
    ]
    citations: list[dict[str, Any]] = []
    for code, detail in result.scenarios.items():
        lines.append(
            f"- {code} ({detail.scenario_name}): giá Net {grounding.format_vnd(detail.net_price_vnd)} · "
            f"tổng HĐMB {grounding.format_vnd(detail.total_contract_price_vnd)} · "
            f"đợt đầu {grounding.format_vnd(detail.initial_cash_outflow_vnd)} · "
            f"tổng tự chi đến nhận nhà {grounding.format_vnd(detail.total_cash_outflow_vnd)} · "
            f"ưu đãi {grounding.format_vnd(detail.benefit_value_vnd)} · khả thi: {'có' if detail.is_feasible else 'không'}"
        )
    lines.append(f"Đề xuất tối ưu theo mục tiêu: {result.recommended_scenario_code}.")
    lines.append(f"Sanity 6 kiểm tra kế toán: {'ĐẠT' if result.sanity_passed else 'KHÔNG ĐẠT'}.")

    citations.append(
        {
            "policy_id": "FCS-v2.6",
            "section": f"Deterministic Math Engine · {unit['unit_code']}",
            "quote": (
                f"calculation_hash={result.calculation_hash[:16]}… · "
                f"khuyến nghị {result.recommended_scenario_code} · sanity_passed={result.sanity_passed}"
            ),
            "source": "DETERMINISTIC_ENGINE",
        }
    )
    if policy:
        citations.extend(
            grounding.policy_citations(
                policy, [r for r in policy.get("rules", []) if r.get("is_selectable")][:3]
            )
        )

    return _dump(
        {
            "tool": "tinh_phuong_an_thanh_toan",
            "summary": _clip("\n".join(lines)),
            "recommended": str(result.recommended_scenario_code),
            "sanity_passed": bool(result.sanity_passed),
            "citations": citations,
        }
    )


# ---------------------------------------------------------------------------
# Tool 3b — Đánh giá vốn tự có (chỉ MỐC TỔNG QUAN, không bảng dòng tiền — chốt P1.2)
# ---------------------------------------------------------------------------
@tool
async def danh_gia_von_tu_co(
    von_tu_co_vnd: int,
    so_phong_ngu: int = 0,
    ma_can: str = "",
    ngay_giao_dich: str = "",
) -> str:
    """Đánh giá nhanh: số vốn tự có của khách đủ hay thiếu bao nhiêu cho một căn.

    Chỉ trả **mốc tổng quan** (tỷ lệ vốn tự có, mức tối thiểu theo phương án vay, thiếu/thừa bao nhiêu)
    — KHÔNG trả bảng dòng tiền chi tiết. Lý do (chốt thiết kế P1.2): khi chưa rõ khách vay ngân hàng nào,
    tiến độ giải ngân và ân hạn nợ gốc, con số chi tiết dễ làm loãng câu trả lời và dễ sai nếu chính sách
    giải ngân thay đổi. Sale muốn chi tiết thì bấm "Xem bảng tính vay" → gọi tool `tinh_phuong_an_thanh_toan`.

    Args:
        von_tu_co_vnd: Vốn tự có của khách (VNĐ).
        so_phong_ngu: Số phòng ngủ cần xét (0 = bỏ qua) — dùng khi Sale chưa chốt mã căn.
        ma_can: Mã căn cụ thể (để trống thì lấy căn mềm nhất của phân khúc `so_phong_ngu`).
        ngay_giao_dich: Ngày giao dịch YYYY-MM-DD (mặc định hôm nay).
    """
    from src.contracts.pricing import PricingInput
    from src.services.pricing.client import PricingClient

    unit = grounding.find_unit(ma_can) if ma_can.strip() else None
    if unit is None and so_phong_ngu:
        segment = inventory_funnel.segment_stats(int(so_phong_ngu))
        unit = segment.softest_unit
    if unit is None:
        return _dump(
            {
                "tool": "danh_gia_von_tu_co",
                "error": "Chưa xác định được căn để đánh giá vốn tự có.",
                "summary": "Cần mã căn (hoặc số phòng ngủ) để đánh giá vốn tự có.",
                "citations": [],
            }
        )

    tx_date = ngay_giao_dich.strip() or date.today().isoformat()
    pricing_input = PricingInput(
        project_id=str(unit.get("project_id")),
        unit_code=str(unit.get("unit_code")),
        listed_price_before_tax_vnd=int(unit.get("listed_price_before_tax_vnd", 0)),
        transaction_date=tx_date,
        own_funds_vnd=int(von_tu_co_vnd or 0),
        monthly_capacity_vnd=0,
        objective=OptimizationObjective.MIN_INITIAL_CASH,
        execution_context="SALES_COPILOT",
    )
    force_mock = os.environ.get("COPILOT_PRICING_VIA_SIDECAR", "false").lower() not in ("true", "1")
    client = PricingClient(force_mock=force_mock)
    result = await client.calculate(pricing_input)

    from src.contracts.pricing import ScenarioCode

    detail = result.scenarios.get(ScenarioCode.PA_VAY) or next(iter(result.scenarios.values()), None)
    if detail is None:  # pragma: no cover - engine luôn trả ít nhất 1 phương án
        return _dump(
            {
                "tool": "danh_gia_von_tu_co",
                "error": "Engine không trả về phương án nào.",
                "summary": "Chưa đánh giá được vốn tự có cho căn này.",
                "citations": [],
            }
        )

    total_contract = int(detail.total_contract_price_vnd or 0)
    # Vốn tự có tối thiểu theo phương án vay = tổng HĐMB − phần ngân hàng giải ngân (dòng 70%).
    bank_leg = next(
        (item for item in detail.payment_schedule if float(getattr(item, "percentage", 0) or 0) >= 70.0),
        None,
    )
    required_own = total_contract - int(getattr(bank_leg, "amount_vnd", 0) or 0) if bank_leg else int(
        detail.initial_cash_outflow_vnd or 0
    )
    own = int(von_tu_co_vnd or 0)
    ratio = (own / total_contract) if total_contract else 0.0
    required_ratio = (required_own / total_contract) if total_contract else 0.0
    gap = required_own - own

    if gap <= 0:
        verdict = (
            f"vốn tự có {grounding.format_vnd(own)} tương đương {ratio:.1%} giá trị HĐMB — "
            f"**đủ** mức tối thiểu theo phương án vay ({required_ratio:.1%} ≈ {grounding.format_vnd(required_own)})"
        )
    else:
        verdict = (
            f"vốn tự có {grounding.format_vnd(own)} tương đương {ratio:.1%} giá trị HĐMB — "
            f"**thiếu** {grounding.format_vnd(gap)} so với mức tối thiểu theo phương án vay "
            f"({required_ratio:.1%} ≈ {grounding.format_vnd(required_own)})"
        )

    summary = (
        f"Đánh giá tổng quan (không phải bảng dòng tiền chi tiết) cho căn {unit['unit_code']} "
        f"({unit.get('bedrooms')}PN, {grounding.project_name(unit.get('project_id'))}): {verdict}.\n"
        f"Tổng giá trị HĐMB tham chiếu: {grounding.format_vnd(total_contract)} (đã gồm VAT và phí bảo trì).\n"
        "Muốn xem bảng dòng tiền từng đợt thì em lập phương án thanh toán chi tiết — "
        "chỉ nên làm khi anh/chị xác nhận khách muốn đi tiếp."
    )

    citations = [
        {
            "policy_id": "FCS-v2.6",
            "section": f"Phương án vay cho {unit['unit_code']}",
            "quote": (
                f"Tổng giá trị HĐMB {grounding.format_vnd(total_contract)} · "
                f"vốn tự có tối thiểu {required_ratio:.1%} ({grounding.format_vnd(required_own)}) · "
                f"khách có {grounding.format_vnd(own)}"
            ),
            "source": "DETERMINISTIC_ENGINE",
        }
    ]

    return _dump(
        {
            "tool": "danh_gia_von_tu_co",
            "summary": _clip(summary),
            "own_funds_vnd": own,
            "own_funds_ratio": round(ratio, 4),
            "required_own_funds_vnd": required_own,
            "required_own_funds_ratio": round(required_ratio, 4),
            "gap_vnd": max(0, gap),
            "unit_code": str(unit.get("unit_code")),
            "citations": citations,
            "data_as_of": _now_iso(),
        }
    )


# ---------------------------------------------------------------------------
# Tool 4 — Kiểm tra phát ngôn F8 / POL-08
# ---------------------------------------------------------------------------
@tool
def kiem_tra_phat_ngon_f8(noi_dung: str) -> str:
    """Kiểm tra một câu/tin nhắn có vi phạm quy chuẩn phát ngôn F8 (POL-08) không.

    Args:
        noi_dung: Nội dung tin nhắn/tư vấn cần kiểm tra.
    """
    response = ComplianceGate().check(ComplianceCheckRequest(message=noi_dung, mode="ON_DRAFT"))
    verdict_map = {
        "SUPPORTED": "ĐƯỢC GỬI",
        "CONDITIONAL": "GỬI CÓ ĐIỀU KIỆN",
        "UNSUPPORTED": "CHƯA ĐỦ CĂN CỨ",
        "PROHIBITED": "BỊ CHẶN",
    }
    lines = [
        f"Kết luận F8: {response.overall_status} ({verdict_map.get(response.overall_status, '')}) "
        f"— hành động: {response.required_action}."
    ]
    for claim in response.claims:
        lines.append(f"- [{claim.tier}] '{claim.claim_text}' — {claim.reason} ({claim.rule_id or 'n/a'})")
    if not response.claims:
        lines.append("- Không phát hiện phát ngôn rủi ro trong bản nháp.")
    return _dump(
        {
            "tool": "kiem_tra_phat_ngon_f8",
            "overall_status": response.overall_status,
            "required_action": response.required_action,
            "summary": _clip("\n".join(lines)),
            "citations": [],
            #: Kết luận do engine kiểm duyệt tất định sinh ra ⇒ là dữ liệu hệ thống, không phải văn model
            #: tự nghĩ. Khai báo để `_finalize` không gắn nhãn "chưa đối chiếu" oan cho lượt này.
            "grounded": True,
            #: Văn bản ĐÃ được kiểm duyệt + từng câu bị gắn cờ. Kết luận bắt buộc phải trích lại chúng
            #: để Sale biết sai ở đâu; lớp chặn rò rỉ đầu ra dùng danh sách này để **miễn** phần trích dẫn
            #: (chỉ phần nằm trong ngoặc kép và khớp đúng văn bản đã kiểm) — xem
            #: `reply_format.mask_quoted_claims`.
            "checked_content": noi_dung,
            "flagged_claims": [claim.claim_text for claim in response.claims if claim.claim_text],
        }
    )


# ---------------------------------------------------------------------------
# Tool 5 — Tra cứu hồ sơ khách hàng (Lead Dossier)
# ---------------------------------------------------------------------------
#: Số hồ sơ tối đa trả về cho Copilot (đủ để Sale chọn, không làm phình Observation).
LEAD_LOOKUP_LIMIT = 5
#: Trần quét dự phòng khi từ khóa không dấu mà tên trong DB có dấu (SQL portable không bỏ dấu được).
LEAD_ACCENT_FALLBACK_SCAN = 200


def _lead_haystack(row: Any) -> str:
    return grounding.normalize(
        f"{getattr(row, 'customer_name', '')} {getattr(row, 'customer_phone', '')} "
        f"{getattr(row, 'customer_phone_masked', '')} {getattr(row, 'dossier_id', '')}"
    )


def _lead_row_line(row: Any) -> str:
    temperature = getattr(row, "lead_temperature", None) or getattr(row, "temperature", "?")
    phone = getattr(row, "customer_phone", None) or getattr(row, "customer_phone_masked", "?")
    return (
        f"- {getattr(row, 'dossier_id', '?')} · {getattr(row, 'customer_name', '?')} · "
        f"{phone} · trạng thái {getattr(row, 'status', '?')} · nhiệt {temperature}"
    )


@tool
async def tra_cuu_ho_so_khach_hang(tu_khoa: str) -> str:
    """Tìm hồ sơ khách hàng (Lead Dossier) theo tên, số điện thoại hoặc mã hồ sơ.

    Args:
        tu_khoa: Tên khách / SĐT / mã hồ sơ (DOS-xxxxxx).
    """
    key = grounding.normalize(tu_khoa).strip()
    raw = (tu_khoa or "").strip()
    if not key:
        return _dump(
            {
                "tool": "tra_cuu_ho_so_khach_hang",
                "error_code": "EMPTY_QUERY",
                "summary": "Chưa có từ khóa tìm hồ sơ.",
                "citations": [],
            }
        )

    import re as _re

    rows: list[Any] = []
    query_mode = "sql_indexed"
    try:
        from sqlalchemy import func, or_, select

        from src.db.models import LeadDossierModel
        from src.db.session import async_session_factory

        digits = _re.sub(r"\D", "", raw)
        pattern = f"%{raw.lower()}%"
        conditions = [
            func.lower(LeadDossierModel.dossier_id).like(pattern),
            func.lower(LeadDossierModel.customer_name).like(pattern),
            func.lower(LeadDossierModel.customer_phone_masked).like(pattern),
        ]
        if digits and digits != raw:
            conditions.append(func.lower(LeadDossierModel.customer_phone_masked).like(f"%{digits}%"))

        async with async_session_factory() as session:
            # Lọc NGAY Ở TẦNG DB (không kéo cả bảng rồi lọc bằng Python như trước).
            stmt = select(LeadDossierModel).where(or_(*conditions)).limit(LEAD_LOOKUP_LIMIT)
            rows = list((await session.execute(stmt)).scalars().all())
            if not rows:
                # Tên trong DB có dấu nhưng Sale gõ không dấu: SQL portable không bỏ dấu được,
                # nên quét có trần (200) rồi khớp bằng Python — vẫn rẻ hơn kéo cả bảng.
                fallback = select(LeadDossierModel).limit(LEAD_ACCENT_FALLBACK_SCAN)
                scanned = (await session.execute(fallback)).scalars().all()
                rows = [row for row in scanned if key in _lead_haystack(row)][:LEAD_LOOKUP_LIMIT]
                if rows:
                    query_mode = "accent_scan_bounded"
    except Exception as exc:  # pragma: no cover — phụ thuộc môi trường DB
        logger.info("Không truy được Lead Dossier (%s).", exc)
        return _dump(
            {
                "tool": "tra_cuu_ho_so_khach_hang",
                "error_code": "DB_DOWN",
                "error": str(exc),
                "summary": (
                    "Không kết nối được cơ sở dữ liệu hồ sơ khách hàng. "
                    "Đề nghị anh/chị thử lại sau hoặc tra cứu trực tiếp trên CRM."
                ),
                "citations": [],
            }
        )

    if not rows:
        return _dump(
            {
                "tool": "tra_cuu_ho_so_khach_hang",
                "error_code": "NOT_FOUND",
                "query_mode": query_mode,
                "summary": f"Không tìm thấy hồ sơ khách hàng khớp '{tu_khoa}'.",
                "citations": [],
            }
        )

    lines = [f"Tìm thấy {len(rows)} hồ sơ khớp '{tu_khoa}':"]
    citations = []
    for row in rows:
        lines.append(_lead_row_line(row))
        phone = getattr(row, "customer_phone", None) or getattr(row, "customer_phone_masked", "?")
        citations.append(
            {
                "policy_id": "CRM-LEAD",
                "section": f"Hồ sơ {getattr(row, 'dossier_id', '?')}",
                "quote": f"{getattr(row, 'customer_name', '?')} · {phone}",
                "source": "CRM_LEAD_DOSSIER",
            }
        )
    return _dump(
        {
            "tool": "tra_cuu_ho_so_khach_hang",
            "query_mode": query_mode,
            "summary": _clip("\n".join(lines)),
            "citations": citations,
        }
    )


# ---------------------------------------------------------------------------
# Tool 6 — Soạn tin tư vấn + tự kiểm F8
# ---------------------------------------------------------------------------
#: Mã trạng thái/kết luận kiểm duyệt → câu tiếng Việt cho banner ghi chú nội bộ.
_COMPLIANCE_STATUS_VI = {
    "SUPPORTED": "ĐƯỢC GỬI",
    "CONDITIONAL": "GỬI CÓ ĐIỀU KIỆN",
    "UNSUPPORTED": "CHƯA ĐỦ CĂN CỨ",
    "PROHIBITED": "BỊ CHẶN",
}
_COMPLIANCE_ACTION_VI = {
    "ALLOW_SEND": "được phép gửi",
    "WARN_CONDITIONAL": "gửi kèm điều kiện, cần đọc lại trước khi gửi",
    "BLOCK_MESSAGE_COMPLIANCE_VIOLATION": "KHÔNG gửi bản nháp này, cần viết lại",
}


def _compliance_note(compliance: Any) -> str:
    """Kết luận kiểm duyệt F8 của bản nháp, dạng câu cho banner ghi chú nội bộ."""
    status = str(getattr(compliance, "overall_status", "") or "")
    action = str(getattr(compliance, "required_action", "") or "")
    status_vi = _COMPLIANCE_STATUS_VI.get(status, status or "chưa rõ")
    action_vi = _COMPLIANCE_ACTION_VI.get(action, action or "chưa rõ")
    note = f"Kiểm duyệt F8 bản nháp: {status_vi} — {action_vi}."
    claims = [c for c in (getattr(compliance, "claims", None) or []) if getattr(c, "claim_text", "")]
    if claims:
        note += " Câu cần sửa: " + "; ".join(f"'{c.claim_text}' ({c.tier})" for c in claims[:3]) + "."
    return note

@tool
async def soan_tin_tu_van(ma_can: str = "", ten_khach: str = "", noi_dung_chinh: str = "") -> str:
    """Soạn bản nháp tin nhắn tư vấn gửi khách và tự kiểm tra F8 trước khi trả về.

    Args:
        ma_can: Mã căn đang tư vấn.
        ten_khach: Tên khách (nếu có) để xưng hô.
        noi_dung_chinh: Ý chính cần truyền đạt trong tin nhắn.
    """
    unit = grounding.find_unit(ma_can) if ma_can else None
    salutation = f"Dạ em chào {ten_khach}," if ten_khach else "Dạ em chào anh/chị,"
    parts = [
        salutation,
        f"em gửi anh/chị thông tin phương án căn {unit['unit_code'] if unit else (ma_can or 'đang quan tâm')} ạ.",
    ]
    if unit:
        parts.append(
            f"Căn {unit['unit_code']} có {unit.get('bedrooms')}PN, {unit.get('area_m2')}m², "
            f"giá niêm yết trước thuế {grounding.format_vnd(unit.get('listed_price_before_tax_vnd'))}."
        )
    if noi_dung_chinh.strip():
        # Chủ đề là một CỤM DANH TỪ ("chiết khấu thanh toán sớm"), không phải câu — phải đóng khung cho
        # ra câu tiếng Việt tử tế, nếu không sẽ dán giữa hai câu và đọc rất kỳ.
        topic = noi_dung_chinh.strip().rstrip(" .,;:")
        topic = topic[0].upper() + topic[1:] if topic else topic
        parts.append(f"Về {topic}, em gửi anh/chị thông tin để mình tham khảo ạ.")
    parts.append(
        "Chính sách ưu đãi áp dụng theo văn bản chính sách đang hiệu lực tại thời điểm giao dịch; "
        "em gửi anh/chị bảng tính chi tiết để mình xem qua nhé."
    )
    draft = " ".join(parts)

    compliance = ComplianceGate().check(ComplianceCheckRequest(message=draft, mode="ON_DRAFT"))
    return _dump(
        {
            "tool": "soan_tin_tu_van",
            "draft_text": draft,
            "compliance_status": compliance.overall_status,
            "required_action": compliance.required_action,
            # `summary` chỉ chứa THÂN TIN đã soạn — đây là văn bản Sale copy gửi khách nguyên văn.
            # Lỗi cũ: gộp cả nhãn kiểm duyệt ("Bản nháp (SUPPORTED)", "F8: ALLOW_SEND") vào summary ⇒
            # bấm "Copy cho khách" là khách nhận luôn mã nội bộ (vi phạm chốt P2.4/K2).
            "summary": draft,
            # Kết luận kiểm duyệt đi đường RIÊNG: `_finalize` gom vào `internal_notes` để UI hiển thị ở
            # banner nội bộ — Sale vẫn thấy, nhưng không bao giờ lọt vào bản gửi khách.
            "internal_notes": _compliance_note(compliance),
            "citations": [],
            #: Bản nháp dựng từ dữ liệu catalog + đã qua cổng kiểm duyệt ⇒ có căn cứ hệ thống **khi tìm
            #: thấy căn**; nếu không có mã căn thì đây chỉ là tin mẫu, không được nhận là đã đối chiếu.
            "grounded": unit is not None,
        }
    )


COPILOT_TOOLS = [
    tra_cuu_chinh_sach,
    tra_cuu_gio_hang,
    tinh_phuong_an_thanh_toan,
    danh_gia_von_tu_co,
    kiem_tra_phat_ngon_f8,
    tra_cuu_ho_so_khach_hang,
    soan_tin_tu_van,
]

TOOLS_BY_NAME = {t.name: t for t in COPILOT_TOOLS}

__all__ = ["COPILOT_TOOLS", "TOOLS_BY_NAME"]
