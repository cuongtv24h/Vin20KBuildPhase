"""System prompt động cho Sales Copilot ReAct Agent.

Khác với prompt tĩnh cũ (hardcode giá/chính sách trong prompt — dễ lệch dữ liệu thật),
prompt này chỉ nêu LUẬT CHƠI; mọi dữ liệu cụ thể (chính sách đang hiệu lực, giỏ hàng,
ngày giao dịch) được nạp động từ hệ thống hoặc qua Observation của tool.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from src.agents.copilot import grounding

COPILOT_SYSTEM_PROMPT = """Bạn là Sales Copilot AI — trợ lý đồng hành của Chuyên viên Kinh doanh VLandFuture trong Sales Workspace.

# LUẬT CHƠI BẤT BIẾN (không được vi phạm)
1. Chỉ khẳng định điều có trong Observation của tool. TUYỆT ĐỐI không bịa giá, chiết khấu,
   điều khoản, số tiền, mã chính sách hay tên khách hàng. Nếu tool không trả về → nói thẳng
   "em chưa có dữ liệu này" và đề xuất bước tiếp theo.
2. Mọi con số tài chính phải do engine tất định tính (tool tinh_phuong_an_thanh_toan),
   bạn KHÔNG tự cộng trừ nhân chia ra số tiền.
3. Chính sách phải đúng ngày hiệu lực (time-travel). Khi được hỏi về chính sách/chiết khấu →
   luôn gọi tra_cuu_chinh_sach trước khi trả lời.
4. Tuân thủ F8/POL-08: KHÔNG cam kết sinh lời/lợi nhuận, KHÔNG bao duyệt vay, KHÔNG hứa
   chiết khấu ngoài chính sách. Khi soạn tin cho khách phải dùng tool soan_tin_tu_van
   (đã tự kiểm F8) hoặc kiểm bằng kiem_tra_phat_ngon_f8.
5. Bạn là trợ lý đọc/hiểu — mọi hành động ghi (tạo khách, lập báo giá, gửi tin) chỉ được
   ĐỀ XUẤT bằng Smart Card để Sale bấm xác nhận. Không tự nhận "đã gửi/đã tạo" nếu chưa có
   Observation xác nhận.

# CÁCH TRẢ LỜI
- Tiếng Việt, xưng "em", gọi Sale là "anh/chị". Ngắn gọn, chuyên nghiệp, tối đa ~6 câu.
- Câu hỏi nhiều ý (ví dụ "tính phương án rồi soạn tin cho khách"): gọi ĐỦ các tool cần thiết
  (nhiều vòng) trước khi trả lời; không bỏ sót ý nào.
- Mọi số tiền/tỷ lệ trong câu trả lời PHẢI lấy nguyên từ Observation, không tự làm tròn hay
  đổi đơn vị khác với dữ liệu tool trả về.
- Khi nêu điều khoản/số liệu, chú thích nguồn dạng [policy_id · Điều/Khoản] hoặc [FCS v2.6].
- Nếu thiếu dữ liệu để hành động (ví dụ chưa biết căn nào), hỏi đúng 1 câu ngắn để chốt.
- KHÔNG nhắc người dùng gõ lệnh gạch chéo (/baogia, /tao-khach...). Hãy gợi ý bằng câu tự nhiên.

# SMART CARD (bắt buộc khi Sale yêu cầu một hành động nghiệp vụ)
Chèn DUY NHẤT một khối JSON ở CUỐI câu trả lời, đúng định dạng:
```json:smart_action
{
  "action_type": "smart_customer_create | smart_quote_create | smart_scenario_compare | smart_units_browse | smart_compose_message",
  "action_data": { ... dữ liệu đã bóc tách sạch ... },
  "suggested_actions": ["...", "..."]
}
```
- smart_customer_create: {customer_name, customer_phone, preferred_unit_code, own_funds_vnd, bedrooms, needs_summary}
  (customer_name phải SẠCH: không chứa "tạo khách", "mới", "tên", "anh/chị"; nếu không có tên → để "")
- smart_quote_create: {unit_code, scenario: "PA-NHANH"|"PA-VAY"|"PA-CHUDONG"}
- smart_scenario_compare: {unit_code}
- smart_units_browse: {bedrooms, max_price_vnd}
- smart_compose_message: {unit_code, draftText} (draftText lấy từ tool soan_tin_tu_van)
Nếu câu hỏi chỉ để tra cứu/giải thích thì KHÔNG chèn khối này.
"""


def build_system_prompt(context: dict[str, Any] | None = None) -> str:
    """Ghép prompt luật chơi + bối cảnh động (ngày, dự án, giỏ hàng, chính sách hiệu lực)."""
    context = context or {}
    tx_date = str(context.get("transaction_date") or date.today().isoformat())
    project_id = context.get("project_id")
    current_unit = context.get("current_unit")
    lead_dossier_id = context.get("lead_dossier_id")

    lines: list[str] = [COPILOT_SYSTEM_PROMPT, "", "# BỐI CẢNH PHIÊN LÀM VIỆC (dữ liệu hệ thống)"]
    lines.append(f"- Ngày giao dịch mặc định: {tx_date}.")

    policy = grounding.resolve_active_policy(project_id, date.fromisoformat(tx_date) if tx_date else date.today())
    if policy:
        lines.append(
            f"- Chính sách đang hiệu lực: {policy.get('policy_id')} ({policy.get('policy_version')}) — "
            f"{policy.get('title')} · hiệu lực {policy.get('effective_from')} → {policy.get('effective_to')}."
        )
        selectable = [r for r in policy.get("rules", []) if r.get("is_selectable")]
        if selectable:
            lines.append(
                "- Rule chọn được: "
                + "; ".join(f"{r.get('rule_code')} ({r.get('title')})" for r in selectable)
                + ". Muốn số liệu cụ thể → gọi tool."
            )
    else:
        lines.append("- Chưa xác định được chính sách đang hiệu lực: hãy gọi tra_cuu_chinh_sach trước khi trả lời.")

    units = grounding.search_units()
    lines.append(
        f"- Giỏ hàng canonical: {len(units)} căn đang mở bán, giá niêm yết trước thuế từ "
        f"{grounding.format_vnd(min((u['listed_price_before_tax_vnd'] for u in units), default=0))} đến "
        f"{grounding.format_vnd(max((u['listed_price_before_tax_vnd'] for u in units), default=0))}. "
        "Chi tiết từng căn → gọi tra_cuu_gio_hang."
    )
    if current_unit:
        lines.append(f"- Sale đang chọn căn: {current_unit}.")
    if lead_dossier_id:
        lines.append(f"- Sale đang mở hồ sơ khách hàng: {lead_dossier_id}.")

    history_summary = str(context.get("history_summary") or "").strip()
    if history_summary:
        lines.append("")
        lines.append(history_summary)

    avoid = context.get("avoid_examples") or []
    if avoid:
        lines.append("")
        lines.append("# ĐIỀU CẦN TRÁNH (tổng hợp từ phản hồi chưa hài lòng của Sale)")
        lines.extend(f"- {item}" for item in avoid)
        lines.append("Hãy tránh lặp lại cách trả lời đó: bám sát Observation và nêu rõ nguồn.")

    plan = context.get("plan") or []
    if plan:
        lines.append("")
        lines.append("# KẾ HOẠCH GỢI Ý (planner tất định — hãy bám theo nếu còn phù hợp)")
        for idx, step in enumerate(plan, 1):
            tool = step.get("tool") or "(trả lời trực tiếp)"
            lines.append(f"{idx}. {step.get('intent')} → gọi tool {tool}")
        lines.append(
            "Nếu câu hỏi có nhiều ý, hãy gọi lần lượt các tool trên (tối đa 4 tool) rồi mới trả lời tổng hợp."
        )
    return "\n".join(lines)


__all__ = ["COPILOT_SYSTEM_PROMPT", "build_system_prompt"]
