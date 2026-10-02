"""ReAct loop cho Sales Copilot (Thought → Action → Observation → … → Final).

Thiết kế:
- Vòng lặp có kiểm soát (`max_iterations`) trên LLM đã `bind_tools`.
- Mọi bước được phát ra dưới dạng `CopilotEvent` để API stream real-time xuống UI
  (UI hiển thị đúng tiến trình suy luận thay vì spinner giả).
- Planner tất định (`planner.py`) chia câu nhiều ý thành nhiều bước và là gợi ý cho LLM.
- Bộ nhớ phiên (`memory.py`) giữ slot căn/hồ sơ/ngày + tóm tắt hội thoại dài.
- Verifier (`verifier.py`) đối chiếu câu trả lời với Observation để chặn số liệu bịa.
- Offline mode: khi LLM lỗi/không có API key, Copilot vẫn chạy ReAct bằng bộ định
  tuyến tất định (intents.py + planner.py) + gọi tool thật → không bao giờ "chết lặng".
- Guardrail đầu vào (prompt injection) & đầu ra (rò rỉ system prompt/credential).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.agents.copilot import anchors, commands, critic, feedback, grounding, intents, memory, planner, verifier
from src.agents.copilot.prompts import build_system_prompt, canonical_facts
from src.agents.copilot.tools import COPILOT_TOOLS, TOOLS_BY_NAME
from src.agents.tools.guardrails import scan_output_leakage, scan_prompt_injection

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 4
MAX_TOOL_CALLS_PER_TURN = 4
MAX_HISTORY_MESSAGES = 6
#: Số lần thử lại khi tool lỗi (lỗi tạm thời). KHÔNG tính vào hạn mức `max_iterations`
#: vì đây là lỗi hạ tầng, không phải một vòng suy luận của agent.
TOOL_RETRIES = 1
TOOL_RETRY_BACKOFF_S = 0.05
#: Trần độ dài Observation gửi vào prompt LLM (giữ đầu — nơi có số liệu chính).
MAX_TOOL_MESSAGE_CHARS = 1_400
#: Ngân sách ngữ cảnh cho toàn bộ Observation của một lượt (P2 — kiểm soát chi phí prompt).
#: Vượt trần thì các Observation sau bị rút gọn mạnh hơn thay vì phình prompt không giới hạn.
MAX_TOTAL_OBSERVATION_CHARS = 6_000
#: Trần rút gọn khi đã cạn ngân sách ngữ cảnh.
TIGHT_TOOL_MESSAGE_CHARS = 700
#: Tool tra cứu **dữ liệu chính sách/giỏ hàng**. Chạy thành công — kể cả khi trả về rỗng
#: ("không có căn nào khớp tiêu chí") — vẫn là câu trả lời có căn cứ: kết luận "0 căn" là một
#: dữ kiện của hệ thống, không phải suy đoán. Trước đây `grounded` chỉ tính `bool(citations)`
#: nên đúng trường hợp này bị dán nhãn "chưa đối chiếu được với dữ liệu chính sách/giỏ hàng".
_GROUNDED_LOOKUP_TOOLS = frozenset(
    {"tra_cuu_chinh_sach", "tra_cuu_gio_hang", "tinh_phuong_an_thanh_toan", "danh_gia_von_tu_co"}
)

_ACTION_BLOCK_RE = re.compile(r"```(?:json:smart_action|json)\s*(\{.*?\})\s*```", re.DOTALL)
_NAME_STRIP_RE = re.compile(
    r"^(?:tạo|thêm|mở|nhập|lưu|đăng\s*ký)?\s*(?:khách(?:\s*hàng)?(?:\s*mới)?|lead|hồ\s*sơ)\s*",
    re.IGNORECASE,
)


@dataclass
class CopilotRequest:
    """Yêu cầu từ Sales Workspace."""

    message: str
    history: list[dict[str, str]] = field(default_factory=list)
    current_unit: str | None = None
    lead_dossier_id: str | None = None
    transaction_date: str | None = None
    project_id: str | None = None


@dataclass
class CopilotEvent:
    """Một bước trong tiến trình ReAct (được stream xuống UI)."""

    type: str  # guardrail | plan | thought | action | observation | final | error
    data: dict[str, Any] = field(default_factory=dict)


def _sanitize_customer_name(raw: str) -> str:
    name = _NAME_STRIP_RE.sub("", str(raw or "")).strip()
    name = re.sub(r"^(?:mới\s+tên|mới\s+là|tên\s+là|tên|mới|anh|chị)\s*", "", name, flags=re.IGNORECASE).strip()
    name = re.sub(r"[,;:\-]?\s*(?:sđt|sdt|phone|điện\s*thoại|\b0\d{8,10}\b).*$", "", name, flags=re.IGNORECASE).strip()
    if len(name) < 2 or grounding.normalize(name) in {"moi", "khach", "khach hang", "khach moi", "anh", "chi", "lead", "null", "none"}:
        return ""
    return name


def _parse_tool_payload(raw: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return {"summary": str(raw)}


def _dedupe_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for c in citations:
        key = (str(c.get("policy_id")), str(c.get("section")))
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def _trim_tool_message(raw: str, limit: int = MAX_TOOL_MESSAGE_CHARS) -> str:
    """Cắt Observation dài trước khi nhét vào prompt: giữ phần ĐẦU (số liệu chính) + citations.

    Không cắt JSON giữa chừng theo kiểu `[:limit]` vì LLM sẽ nhận JSON hỏng; thay vào đó payload
    vẫn là JSON hợp lệ nhưng `summary` được rút gọn.
    """
    if len(raw) <= limit:
        return raw
    payload = _parse_tool_payload(raw)
    summary = str(payload.get("summary", ""))
    head = max(200, limit - 400)
    payload["summary"] = summary[:head] + " …(đã lược bớt để tiết kiệm ngữ cảnh)"
    payload["truncated"] = True
    return json.dumps(payload, ensure_ascii=False, default=str)


def _tool_cache_key(call: dict[str, Any]) -> str:
    """Khoá cache cho một tool call: tên tool + tham số đã chuẩn hoá thứ tự.

    Cùng một câu hỏi, LLM thỉnh thoảng gọi lại y hệt một tool (ví dụ vừa tra giá vừa tra chính
    sách ở hai vòng khác nhau). Kết quả trong cùng một lượt là bất biến, nên trả lại từ cache
    vừa nhanh hơn vừa không tính thêm ngân sách ngữ cảnh.
    """
    name = str(call.get("name") or "")
    args = call.get("args") or {}
    try:
        frozen = json.dumps(args, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):  # pragma: no cover — args không serialize được là bất thường
        frozen = repr(args)
    return f"{name}::{frozen}"


def _trim_with_budget(raw: str, remaining_budget: int) -> str:
    """Rút gọn Observation theo ngân sách còn lại của lượt."""
    limit = MAX_TOOL_MESSAGE_CHARS if remaining_budget >= MAX_TOOL_MESSAGE_CHARS else TIGHT_TOOL_MESSAGE_CHARS
    return _trim_tool_message(raw, limit=min(limit, max(remaining_budget, 200)))


async def _execute_tool(call: dict[str, Any]) -> tuple[dict[str, Any], str, int]:
    """Thực thi 1 tool call; trả về (payload, raw JSON cho ToolMessage, số lần thử).

    Lỗi hạ tầng (timeout, DB down) được thử lại 1 lần với backoff ngắn; lỗi vẫn còn thì trả
    Observation có `error_code` để LLM biết đường xử lý thay vì im lặng coi như rỗng.
    """
    name = str(call.get("name") or "")
    args = call.get("args") or {}
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        payload = {
            "summary": f"Tool '{name}' không tồn tại trong danh mục.",
            "citations": [],
            "error_code": "UNKNOWN_TOOL",
        }
        return payload, json.dumps(payload, ensure_ascii=False), 0

    last_exc: Exception | None = None
    for attempt in range(1, TOOL_RETRIES + 2):
        try:
            raw = await tool.ainvoke(args)
            payload = _parse_tool_payload(str(raw))
            payload.setdefault("tool", name)
            return payload, _trim_tool_message(str(raw)), attempt
        except Exception as exc:  # noqa: BLE001 — lỗi tool không được làm sập phiên chat
            last_exc = exc
            if attempt <= TOOL_RETRIES:
                logger.info("Tool %s lỗi lần %s (%s) — thử lại.", name, attempt, exc)
                await asyncio.sleep(TOOL_RETRY_BACKOFF_S * attempt)

    payload = {
        "tool": name,
        "error_code": "TOOL_ERROR",
        "error": str(last_exc),
        "summary": (
            f"Tool {name} gặp lỗi khi thực thi sau {TOOL_RETRIES + 1} lần thử: {last_exc}. "
            "Đề nghị thử lại hoặc xử lý thủ công."
        ),
        "citations": [],
    }
    return payload, json.dumps(payload, ensure_ascii=False), TOOL_RETRIES + 1


def _latest_data_as_of(observations: list[dict[str, Any]]) -> str | None:
    """Mốc thời gian dữ liệu mới nhất trong các Observation (chốt P1.6)."""
    stamps = [str(obs.get("data_as_of")) for obs in observations if obs.get("data_as_of")]
    return max(stamps) if stamps else None


class IntentResultLike:
    """Protocol mềm để type-check nhẹ (tránh import vòng)."""

    intent: str


def _finalize(
    raw_text: str,
    observations: list[dict[str, Any]],
    deterministic_action: dict[str, Any] | None,
    suggested_default: list[str],
    intent: IntentResultLike,
    *,
    plan: list[planner.PlanStep] | None = None,
    slots: memory.SessionSlots | None = None,
    question: str = "",
    known_context: str = "",
) -> dict[str, Any]:
    """Hậu xử lý câu trả lời cuối: tách Smart Card, gộp citation, kiểm rò rỉ, kiểm chứng số liệu.

    `question` là câu hỏi gốc của Sale — cần để verifier không gắn cờ oan những con số do chính
    người dùng nêu ra (ví dụ ngân sách 2 tỷ) mà câu trả lời chỉ nhắc lại.

    `known_context` là **dữ liệu canonical** đã nạp vào prompt (dải giá giỏ hàng, chính sách hiệu lực) —
    xem `prompts.canonical_facts`. Cũng là số liệu thật của hệ thống.
    """
    action_type: str | None = None
    action_data: dict[str, Any] | None = None
    suggested_actions = list(suggested_default)

    match = _ACTION_BLOCK_RE.search(raw_text)
    if match:
        try:
            parsed = json.loads(match.group(1))
            action_type = parsed.get("action_type")
            action_data = parsed.get("action_data")
            if parsed.get("suggested_actions"):
                suggested_actions = [str(s) for s in parsed["suggested_actions"]]
        except json.JSONDecodeError:
            logger.warning("Không parse được khối json:smart_action từ LLM.")
        text = _ACTION_BLOCK_RE.sub("", raw_text).strip()
    else:
        text = raw_text.strip()

    # LLM quên Smart Card nhưng ý định nghiệp vụ rõ ràng → bổ sung từ lớp tất định
    if action_type is None and deterministic_action:
        action_type = deterministic_action.get("action_type")
        action_data = deterministic_action.get("action_data")

    if action_type == intents.INTENT_CREATE_CUSTOMER and isinstance(action_data, dict):
        action_data["customer_name"] = _sanitize_customer_name(action_data.get("customer_name", ""))

    leak = scan_output_leakage(text)
    if not leak.is_safe:
        logger.warning("Chặn rò rỉ ở output Copilot: %s", leak.detected_patterns)
        text = (
            "Em xin phép không hiển thị nội dung nội bộ đó. "
            "Anh/chị cần em hỗ trợ tra chính sách, xem giỏ hàng hay lập báo giá không ạ?"
        )
        action_type, action_data = None, None

    citations = _dedupe_citations([c for obs in observations for c in (obs.get("citations") or [])])
    tool_calls = [obs.get("tool") for obs in observations if obs.get("tool")]
    # `grounded` = câu trả lời dựa trên dữ liệu hệ thống. Ba đường:
    #  1. Có citation (đường thường gặp).
    #  2. Tool tra cứu chính sách/giỏ hàng đã chạy **thành công** — kể cả trả về rỗng, vì "0 căn khớp"
    #     là kết luận lấy từ dữ liệu (lỗi cũ: trường hợp này bị coi là "chưa đối chiếu").
    #  3. Câu chào hỏi/xã giao (không cần dữ liệu).
    lookup_ok = any(
        obs.get("tool") in _GROUNDED_LOOKUP_TOOLS
        and not obs.get("error")
        and not obs.get("error_code")
        for obs in observations
    )
    grounded = bool(citations) or lookup_ok or intent.intent in (intents.INTENT_SMALL_TALK,)

    # Prompt đã dặn không nhắc lệnh gạch chéo, nhưng model vẫn có thể nhắc — chặn ở output.
    text = commands.strip_command_mentions(text)

    if not text:
        text = "Em đã ghi nhận yêu cầu. Anh/chị cần em làm rõ thêm bước nào không ạ?"

    # Verifier: mọi số liệu/mã văn bản trong câu trả lời phải có trong Observation (hoặc trong câu
    # hỏi của Sale — số người dùng tự nêu không tính là bịa).
    check = verifier.verify_reply(text, observations, question=question, context=known_context)

    # Ghi chú nội bộ (chốt P2.4): GIỮ SẠCH nội dung trả lời — mọi cảnh báo đi vào trường riêng
    # `internal_notes`, UI hiển thị ở banner riêng. Nhờ vậy Sale bấm "Copy cho khách" là ra văn bản
    # gửi được ngay, không dính câu quy trình nội bộ.
    notes: list[str] = []
    if not check.verified:
        logger.warning("Verifier phát hiện số liệu không có nguồn: %s", check.unsupported)
        notes.append(
            "có số liệu chưa đối chiếu được với dữ liệu hệ thống ("
            + ", ".join(check.unsupported[:3])
            + ")"
        )
    if not grounded and intent.intent not in (intents.INTENT_SMALL_TALK,):
        notes.append("nội dung này chưa đối chiếu với dữ liệu chính sách/giỏ hàng")

    # Mỏ neo `[n]` do MÁY chèn (chốt P2.3) — sau khi đã có nội dung, trước khi soi critic, để critic
    # chỉ còn nhắc khi con số thật sự không có nguồn nào để trỏ tới.
    anchored = anchors.annotate_reply(text, citations, question=question)
    text = anchored.text

    # Critic vòng 2 (P2): chỉ soi lượt quan trọng — câu có số tiền/ưu đãi hoặc câu soạn tin, tuân thủ.
    # Kết quả trả về ở trường `critique` (UI hiển thị banner riêng) — **không** chèn thêm câu vào nội
    # dung trả lời.
    review = critic.Critique()
    if critic.is_high_stakes(text, intent.intent):
        review = critic.critique_reply(text, intent=intent.intent, observations=observations)

    # Lời nhắc của critic **không** gộp vào `internal_notes`: nó đã có trường `critique` riêng, UI gộp
    # cả hai vào MỘT banner "Ghi chú nội bộ" — gộp ở backend sẽ hiển thị lặp hai lần.

    return {
        "reply": text,
        "action_type": action_type,
        "action_data": action_data,
        "suggested_actions": suggested_actions,
        "citations": citations,
        #: Mỏ neo `[n]` → căn cứ: UI biến `[n]` thành nút bấm mở đúng nguồn (chốt P2.1).
        "anchors": [a.as_dict() for a in anchored.anchors],
        #: Số do Sale tự nêu đã được in đậm kèm nhãn (chốt P2.2) — không gắn mỏ neo.
        "labeled_inputs": anchored.labeled_inputs,
        #: Ghi chú kiểm duyệt nội bộ — KHÔNG nằm trong `reply` (chốt P2.4).
        "internal_notes": " · ".join(notes),
        #: Mốc thời gian dữ liệu để UI hiển thị watermark (chốt P1.6), không đưa vào văn phong.
        "data_as_of": _latest_data_as_of(observations),
        "grounded": grounded,
        "tools_used": tool_calls,
        "verified": check.verified,
        "verification": check.as_dict(),
        "critique": review.as_dict(),
        "plan": [{"intent": s.intent, "tool": s.tool, "reason": s.reason} for s in (plan or [])],
        "slots": (slots or memory.SessionSlots()).as_dict(),
    }


def _format_budget_short(amount_vnd: int) -> str:
    """`2000000000` → `2 tỷ` — dùng trong nhãn nút hành động nhanh cho gọn (chốt K4)."""
    if amount_vnd >= 1_000_000_000:
        value = amount_vnd / 1_000_000_000
        text = f"{value:.1f}".rstrip("0").rstrip(".")
        return f"{text} tỷ"
    if amount_vnd >= 1_000_000:
        value = amount_vnd / 1_000_000
        text = f"{value:.0f}"
        return f"{text} triệu"
    return grounding.format_vnd(amount_vnd)


def _default_suggestions(
    intent: str,
    unit_code: str | None,
    entities: dict[str, Any] | None = None,
) -> list[str]:
    """Nút hành động nhanh (chốt K4): thay vì viết dài, gợi ý việc bấm được ngay.

    Nhãn phải **mang theo ngữ cảnh** (số phòng ngủ, ngân sách) để khi Sale bấm, câu gửi vào khung chat
    vẫn đủ dữ liệu — không thì Copilot phải hỏi lại, mất đúng cái lợi của nút bấm.
    """
    unit = unit_code or "ZEN-A-1205"
    entities = entities or {}
    bedrooms = int(entities.get("bedrooms") or 0)
    budget = int(entities.get("amount_vnd") or 0)
    budget_text = f" (ngân sách {_format_budget_short(budget)})" if budget else ""
    if intent == intents.INTENT_CREATE_CUSTOMER:
        return ["Lưu khách hàng vào CRM", f"Tạo báo giá căn {unit}", f"So sánh 3 phương án căn {unit}"]
    if intent in (intents.INTENT_CREATE_QUOTE, intents.INTENT_COMPARE_SCENARIOS):
        return ["Trình duyệt báo giá", "Xem bảng tính vay chi tiết", "Soạn tin nhắn gửi khách"]
    if intent == intents.INTENT_ASSESS_FUNDS:
        # K4: gợi ý bằng NÚT BẤM thay vì viết dài — Sale bấm là ra bảng dòng tiền chi tiết.
        return ["Xem bảng tính vay chi tiết", f"Tạo báo giá căn {unit}", "Soạn tin nhắn gửi khách"]
    if intent == intents.INTENT_COMPOSE_MESSAGE:
        return ["Kiểm tra lại tuân thủ F8", "Lập báo giá đính kèm", "Đổi văn phong thân mật hơn"]
    if intent == intents.INTENT_BROWSE_UNITS:
        chips: list[str] = []
        if bedrooms:
            lower = max(1, bedrooms - 1)
            chips.append(f"Xem bảng tính vay chi tiết cho căn {bedrooms} ngủ{budget_text}")
            chips.append(f"Gửi danh sách căn {bedrooms} ngủ đang mở bán")
            chips.append(f"Mở rộng sang căn {lower}PN+1{budget_text}")
        else:
            chips = [
                "Xem chi tiết căn rẻ nhất",
                "Gửi danh sách căn đang mở bán",
                "So sánh phương án căn này",
            ]
        return chips
    return ["Tra cứu chính sách đang hiệu lực", "Xem giỏ hàng còn căn nào", "Tạo báo giá cho khách"]


def _legacy_tool_plan(request: CopilotRequest, intent: intents.IntentResult) -> list[tuple[str, dict[str, Any], str]]:
    """Kế hoạch dự phòng theo intent đơn (giữ tương thích khi planner không tách được gì)."""
    ctx_unit = request.current_unit or intent.entities.get("unit_code") or "ZEN-A-1205"
    tx_date = request.transaction_date or ""
    if intent.intent == intents.INTENT_LOOKUP_POLICY:
        return [("tra_cuu_chinh_sach", {"cau_hoi": request.message, "ngay_hieu_luc": tx_date}, "Tra cứu chính sách hiệu lực")]
    if intent.intent == intents.INTENT_BROWSE_UNITS:
        return [
            (
                "tra_cuu_gio_hang",
                {
                    "so_phong_ngu": intent.entities.get("bedrooms") or 0,
                    "gia_toi_da_vnd": intent.entities.get("amount_vnd") or 0,
                    "ma_can": intent.entities.get("unit_code") or "",
                },
                "Lọc giỏ hàng theo tiêu chí",
            )
        ]
    if intent.intent == intents.INTENT_ASSESS_FUNDS:
        return [
            (
                "danh_gia_von_tu_co",
                {
                    "von_tu_co_vnd": intent.entities.get("amount_vnd") or 0,
                    "so_phong_ngu": intent.entities.get("bedrooms") or 0,
                    "ma_can": intent.entities.get("unit_code") or "",
                    "ngay_giao_dich": tx_date,
                },
                "Đánh giá tổng quan vốn tự có (không bảng dòng tiền chi tiết)",
            )
        ]
    if intent.intent in (intents.INTENT_CREATE_QUOTE, intents.INTENT_COMPARE_SCENARIOS):
        return [
            (
                "tinh_phuong_an_thanh_toan",
                {
                    "ma_can": ctx_unit,
                    "von_tu_co_vnd": intent.entities.get("amount_vnd") or 0,
                    "muc_tieu": "MIN_INITIAL_CASH",
                    "ngay_giao_dich": tx_date,
                },
                "Tính 3 phương án bằng engine tất định",
            ),
            ("tra_cuu_chinh_sach", {"cau_hoi": "chiết khấu ưu đãi", "ngay_hieu_luc": tx_date}, "Đối chiếu chính sách"),
        ]
    if intent.intent == intents.INTENT_COMPOSE_MESSAGE:
        return [("soan_tin_tu_van", {"ma_can": ctx_unit, "ten_khach": "", "noi_dung_chinh": ""}, "Soạn nháp & tự kiểm F8")]
    if intent.intent == intents.INTENT_LOOKUP_CUSTOMER:
        return [("tra_cuu_ho_so_khach_hang", {"tu_khoa": request.message}, "Tra hồ sơ khách hàng")]
    if intent.intent == intents.INTENT_CHECK_F8:
        return [("kiem_tra_phat_ngon_f8", {"noi_dung": request.message}, "Kiểm tra phát ngôn F8")]
    if intent.intent == intents.INTENT_CREATE_CUSTOMER:
        return [("tra_cuu_gio_hang", {"so_phong_ngu": intent.entities.get("bedrooms") or 0, "ma_can": ctx_unit}, "Xác minh căn phù hợp")]
    return []


async def _run_offline_react(
    request: CopilotRequest,
    intent: intents.IntentResult,
    observations: list[dict[str, Any]],
    plan: list[planner.PlanStep] | None = None,
) -> AsyncIterator[CopilotEvent]:
    """ReAct tất định khi không có LLM: vẫn gọi tool thật và phát trace thật."""
    tool_plan: list[tuple[str, dict[str, Any], str]] = [
        (step.tool, step.args, step.reason) for step in (plan or []) if step.tool
    ]
    if not tool_plan:
        tool_plan = _legacy_tool_plan(request, intent)
    if not tool_plan:
        return

    executed = 0
    for name, args, reason in tool_plan[:MAX_TOOL_CALLS_PER_TURN]:
        yield CopilotEvent("action", {"tool": name, "args": args, "reason": reason})
        payload, _raw, attempts = await _execute_tool({"name": name, "args": args})
        payload["tool"] = name
        observations.append(payload)
        executed += 1
        yield CopilotEvent(
            "observation",
            {
                "tool": name,
                "ok": not payload.get("error") and not payload.get("error_code"),
                "error_code": payload.get("error_code"),
                "attempts": attempts,
                "summary": str(payload.get("summary", ""))[:1200],
                "citations": payload.get("citations") or [],
                # Trường máy đọc được để eval/CI kiểm tự động (P3.2) — không đưa vào câu trả lời.
                "match_count": payload.get("match_count"),
                "segment_check": payload.get("segment_check"),
                "data_as_of": payload.get("data_as_of"),
            },
        )

    # Lọc rỗng không phải ngõ cụt (chốt P1.1/P1.2): nếu Sale có nêu ngân sách và số phòng ngủ, đi tiếp
    # một bước **tổng quan** vốn tự có (KHÔNG phải bảng dòng tiền chi tiết) để câu trả lời có mốc
    # "khả thi tới đâu / còn thiếu bao nhiêu" thay vì dừng ở "không có căn nào".
    follow_up = _own_funds_follow_up(observations, intent, executed)
    if follow_up is not None:
        name, args, reason = follow_up
        yield CopilotEvent("action", {"tool": name, "args": args, "reason": reason})
        payload, _raw, attempts = await _execute_tool({"name": name, "args": args})
        payload["tool"] = name
        observations.append(payload)
        yield CopilotEvent(
            "observation",
            {
                "tool": name,
                "ok": not payload.get("error") and not payload.get("error_code"),
                "error_code": payload.get("error_code"),
                "attempts": attempts,
                "summary": str(payload.get("summary", ""))[:1200],
                "citations": payload.get("citations") or [],
                # Trường máy đọc được để eval/CI kiểm tự động (P3.2) — không đưa vào câu trả lời.
                "match_count": payload.get("match_count"),
                "segment_check": payload.get("segment_check"),
                "data_as_of": payload.get("data_as_of"),
            },
        )


def _own_funds_follow_up(
    observations: list[dict[str, Any]],
    intent: intents.IntentResult,
    executed: int,
) -> tuple[str, dict[str, Any], str] | None:
    """Bước đi tiếp khi lọc giỏ hàng ra rỗng mà Sale có nêu ngân sách + số phòng ngủ."""
    if executed >= MAX_TOOL_CALLS_PER_TURN:
        return None
    browse = next((o for o in observations if o.get("tool") == "tra_cuu_gio_hang"), None)
    if browse is None or int(browse.get("match_count") or 0) != 0:
        return None
    budget = int(intent.entities.get("amount_vnd") or 0)
    bedrooms = int(intent.entities.get("bedrooms") or 0)
    if not budget or not bedrooms:
        return None
    return (
        "danh_gia_von_tu_co",
        {
            "von_tu_co_vnd": budget,
            "so_phong_ngu": bedrooms,
            "ngay_giao_dich": str(intent.entities.get("transaction_date") or ""),
        },
        "Lọc rỗng → ước lượng tổng quan vốn tự có để có hướng đi tiếp",
    )


async def stream_copilot(
    request: CopilotRequest,
    *,
    llm: Any | None = None,
    llm_factory: Callable[[], Any] | None = None,
    max_iterations: int = MAX_ITERATIONS,
) -> AsyncIterator[CopilotEvent]:
    """Chạy vòng lặp ReAct và phát từng bước xuống UI."""
    # Lệnh gạch chéo (/chinh-sach, /baogia…) phải được dịch sang câu tự nhiên TRƯỚC khi vào LLM,
    # nếu không model sẽ lặp lại đúng chuỗi lệnh đó trong câu trả lời và làm lệch nội dung.
    message = commands.normalize_user_message(request.message)
    request = CopilotRequest(
        message=message,
        history=commands.sanitize_history(request.history),
        current_unit=request.current_unit,
        lead_dossier_id=request.lead_dossier_id,
        transaction_date=request.transaction_date,
        project_id=request.project_id,
    )
    intent = intents.detect_intent(message)

    # 0) Bộ nhớ phiên: điền slot còn thiếu từ lịch sử hội thoại
    slots = memory.resolve_slots(
        current_unit=request.current_unit,
        lead_dossier_id=request.lead_dossier_id,
        transaction_date=request.transaction_date,
        message=message,
        history=request.history,
    )
    enriched_entity = memory.enrich_entity_with_slots(intent.entities, slots)
    intent = intents.IntentResult(intent.intent, intent.confidence, enriched_entity, intent.matched_keywords)

    # 0b) Planner: chia câu nhiều ý thành nhiều bước
    plan = planner.decompose(message, enriched_entity)
    observations: list[dict[str, Any]] = []
    deterministic_action = intents.build_action_card(
        message, intent, {"current_unit": slots.current_unit or request.current_unit}
    )

    # 1) Guardrail đầu vào
    scan = scan_prompt_injection(message)
    if not scan.is_safe and scan.risk_level in ("HIGH", "CRITICAL"):
        yield CopilotEvent(
            "guardrail",
            {"is_safe": False, "risk_level": scan.risk_level, "patterns": scan.detected_patterns},
        )
        yield CopilotEvent(
            "final",
            {
                "reply": (
                    "Em nhận thấy nội dung này cố tình thay đổi quy tắc hoạt động của hệ thống nên xin phép "
                    "không thực hiện. Anh/chị cần em hỗ trợ nghiệp vụ bình thường không ạ?"
                ),
                "action_type": None,
                "action_data": None,
                "suggested_actions": _default_suggestions(intents.INTENT_SMALL_TALK, request.current_unit),
                "citations": [],
                "grounded": False,
                "tools_used": [],
                "verified": False,
                "verification": {"verified": False, "reason": "input bị chặn bởi guardrail", "unsupported_claims": []},
                "plan": [],
                "slots": slots.as_dict(),
                "guardrail": scan.model_dump(),
                "iterations": 0,
                "mode": "guardrail",
            },
        )
        return

    # 2) Chuẩn bị LLM
    def _resolve_llm() -> Any:
        if llm is not None:
            return llm
        if llm_factory is not None:
            return llm_factory()
        from src.services.llm import get_llm

        return get_llm()

    llm_with_tools = None
    offline_reason: str | None = None
    try:
        base_llm = _resolve_llm()
        llm_with_tools = base_llm.bind_tools(COPILOT_TOOLS) if hasattr(base_llm, "bind_tools") else base_llm
    except Exception as exc:  # noqa: BLE001
        offline_reason = str(exc)
        logger.warning("Không khởi tạo được LLM cho Copilot (%s) — dùng offline ReAct.", exc)

    prompt_context = {
        "current_unit": slots.current_unit or request.current_unit,
        "lead_dossier_id": slots.lead_dossier_id or request.lead_dossier_id,
        "transaction_date": slots.transaction_date or request.transaction_date,
        "project_id": request.project_id,
        "plan": [{"intent": s.intent, "tool": s.tool} for s in plan],
        "history_summary": memory.summarize_history(request.history),
        # Học từ phản hồi (P2): các lượt từng bị chê, nhắc để không lặp lại cách trả lời đó.
        "avoid_examples": feedback.few_shot_hints(),
    }
    system_prompt = build_system_prompt(prompt_context)
    # Chỉ phần **dữ liệu canonical** (không gồm `avoid_examples` do LLM tổng hợp) mới được coi là
    # nguồn tham chiếu cho verifier.
    canonical_reference = "\n".join(canonical_facts(prompt_context))
    messages: list[Any] = [SystemMessage(content=system_prompt)]
    for item in (request.history or [])[-MAX_HISTORY_MESSAGES:]:
        role = str(item.get("role", "")).lower()
        content = str(item.get("content", "") or "")
        if not content:
            continue
        messages.append(HumanMessage(content=content) if role == "user" else AIMessage(content=content))
    messages.append(HumanMessage(content=message))

    # 3) Vòng lặp ReAct
    if llm_with_tools is not None:
        try:
            if plan:
                yield CopilotEvent(
                    "plan",
                    {
                        "steps": [{"intent": s.intent, "tool": s.tool, "reason": s.reason} for s in plan],
                        "summary": planner.plan_summary(plan),
                    },
                )
            tool_cache: dict[str, tuple[dict[str, Any], str, int]] = {}
            cached_hits = 0
            observation_chars = 0
            for iteration in range(1, max_iterations + 1):
                response = await llm_with_tools.ainvoke(messages)
                messages.append(response)

                thoughts = str(getattr(response, "content", "") or "").strip()
                if thoughts:
                    yield CopilotEvent("thought", {"text": thoughts[:1200], "iteration": iteration})

                tool_calls = list(getattr(response, "tool_calls", None) or [])
                if not tool_calls:
                    final = _finalize(
                        str(getattr(response, "content", "") or ""),
                        observations,
                        deterministic_action,
                        _default_suggestions(intent.intent, slots.current_unit or request.current_unit, intent.entities),
                        intent,
                        plan=plan,
                        slots=slots,
                        question=request.message,
                        known_context=canonical_reference,
                    )
                    final["iterations"] = iteration
                    final["mode"] = "react"
                    final["context_budget"] = {
                        "observation_chars": observation_chars,
                        "limit_chars": MAX_TOTAL_OBSERVATION_CHARS,
                        "cached_tool_results": cached_hits,
                        "trimmed": observation_chars >= MAX_TOTAL_OBSERVATION_CHARS,
                    }
                    yield CopilotEvent("final", final)
                    return

                for call in tool_calls[:MAX_TOOL_CALLS_PER_TURN]:
                    name = str(call.get("name") or "")
                    args = call.get("args") or {}
                    yield CopilotEvent("action", {"tool": name, "args": args, "reason": "LLM quyết định gọi tool"})

                    cache_key = _tool_cache_key(call)
                    cached = tool_cache.get(cache_key)
                    if cached is not None:
                        payload, raw, attempts = cached
                        cached_hits += 1
                    else:
                        payload, raw, attempts = await _execute_tool(call)
                        raw = _trim_with_budget(raw, MAX_TOTAL_OBSERVATION_CHARS - observation_chars)
                        payload["tool"] = name
                        tool_cache[cache_key] = (payload, raw, attempts)
                        observation_chars += len(raw)
                    observations.append(payload)
                    yield CopilotEvent(
                        "observation",
                        {
                            "tool": name,
                            "ok": not payload.get("error") and not payload.get("error_code"),
                            "error_code": payload.get("error_code"),
                            "attempts": attempts,
                            "cached": cached is not None,
                            "summary": str(payload.get("summary", ""))[:1200],
                            "citations": payload.get("citations") or [],
                        },
                    )
                    messages.append(ToolMessage(content=raw, tool_call_id=str(call.get("id") or name)))

            # Hết vòng lặp mà LLM chưa chốt → tổng hợp từ observation
            final = _finalize(
                "Em đã thu thập đủ dữ liệu cần thiết. Anh/chị xem tóm tắt bên dưới và cho em biết bước tiếp theo nhé.",
                observations,
                deterministic_action,
                _default_suggestions(intent.intent, slots.current_unit or request.current_unit, intent.entities),
                intent,
                plan=plan,
                slots=slots,
                question=request.message,
                known_context=canonical_reference,
            )
            final["iterations"] = max_iterations
            final["mode"] = "react"
            final["truncated"] = True
            yield CopilotEvent("final", final)
            return
        except Exception as exc:  # noqa: BLE001 — rơi về offline ReAct thay vì lỗi 500
            offline_reason = str(exc)
            logger.warning("ReAct loop lỗi (%s) — chuyển offline ReAct.", exc)

    # 4) Offline ReAct fallback
    yield CopilotEvent(
        "guardrail",
        {"is_safe": True, "risk_level": scan.risk_level, "patterns": scan.detected_patterns, "degraded": bool(offline_reason)},
    )
    if plan:
        yield CopilotEvent(
            "plan",
            {
                "steps": [{"intent": s.intent, "tool": s.tool, "reason": s.reason} for s in plan],
                "summary": planner.plan_summary(plan),
            },
        )
    async for event in _run_offline_react(request, intent, observations, plan):
        yield event

    summary_bits = [str(o.get("summary", "")) for o in observations if o.get("summary")]
    if summary_bits:
        reply = "\n\n".join(summary_bits)
    else:
        reply = (
            "Em đã ghi nhận yêu cầu của anh/chị nhưng chưa tra được dữ liệu tương ứng. "
            "Anh/chị nói rõ hơn mã căn hoặc nội dung cần tra giúp em nhé."
        )
    if intent.intent == intents.INTENT_CREATE_CUSTOMER:
        name = intent.entities.get("customer_name") or "khách hàng"
        reply = (
            f"Em đã bóc tách hồ sơ cho {name}"
            + (f" (SĐT {intent.entities.get('customer_phone')})" if intent.entities.get("customer_phone") else "")
            + ". Anh/chị kiểm tra thông tin trên thẻ và bấm Khởi tạo ngay để lưu vào CRM nhé."
        )
    final = _finalize(
        reply,
        observations,
        deterministic_action,
        _default_suggestions(intent.intent, slots.current_unit or request.current_unit, intent.entities),
        intent,
        plan=plan,
        slots=slots,
        question=request.message,
        known_context=canonical_reference,
    )
    final["iterations"] = 1
    final["mode"] = "offline_react"
    final["degraded_reason"] = offline_reason
    final["context_budget"] = {
        "observation_chars": sum(len(str(o.get("summary", ""))) for o in observations),
        "limit_chars": MAX_TOTAL_OBSERVATION_CHARS,
        "cached_tool_results": 0,
        "trimmed": False,
    }
    yield CopilotEvent("final", final)


__all__ = ["CopilotEvent", "CopilotRequest", "stream_copilot"]
