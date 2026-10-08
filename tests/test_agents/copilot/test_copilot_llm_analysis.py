"""Copilot đường ONLINE: LLM phải là lớp **phân tích**, không phải lớp diễn đạt lại từ khóa.

Người dùng chốt (đợt 26): "Copilot thông minh nhờ đưa ngay dữ liệu câu hỏi của Sale vào để LLM phân
tích". Bộ test này khoá đúng điều đó ở đường ReAct (có LLM):

1. `build_system_prompt` chứa **câu hỏi nguyên văn** + **tiêu chí đã bóc tách** (diện tích ±10%, ngân sách,
   số phòng ngủ, mã căn, ngày giao dịch) và nói rõ đó là *gợi ý* — model tự sửa theo câu hỏi.
2. Kế hoạch của planner tất định chỉ được nêu như đề xuất, không phải mệnh lệnh.
3. Khi model tự quyết gọi tool giỏ hàng với tham số diện tích, tham số đó chạy thật tới tool (không bị
   lớp từ khóa ghi đè).
"""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.messages import AIMessage

from src.agents.copilot import grounding, intents, memory, planner, prompts
from src.agents.copilot.graph import CopilotRequest, stream_copilot

REPORTED_QUESTION = "Chị ơi tìm giúp em căn 70m² tầm 3 tỷ"


def _context_for(question: str) -> dict[str, Any]:
    """Dựng context y như `graph.stream_copilot` làm cho một câu hỏi thật."""
    intent = intents.detect_intent(question)
    slots = memory.resolve_slots(message=question)
    enriched = memory.enrich_entity_with_slots(intent.entities, slots)
    plan = planner.decompose(question, enriched)
    return {
        "question": question,
        "entities": enriched,
        "transaction_date": "2026-09-26",
        "plan": [{"intent": s.intent, "tool": s.tool} for s in plan],
    }


def test_system_prompt_carries_raw_question_and_extracted_criteria() -> None:
    prompt = prompts.build_system_prompt(_context_for(REPORTED_QUESTION))

    # 1. Câu hỏi nguyên văn — LLM đọc thẳng câu của Sale, không chỉ nhận kết quả bóc tách.
    assert REPORTED_QUESTION in prompt
    # 2. Tiêu chí bóc tách đi kèm, đúng số: diện tích đã nới ±10% và ngân sách.
    assert "63–77m²" in prompt
    assert "3.000.000.000 ₫" in prompt
    # 3. Nói rõ model chịu trách nhiệm phân tích + được phép sửa tiêu chí gợi ý.
    assert "chịu trách nhiệm phân tích" in prompt
    assert "chỉ là **gợi ý**" in prompt


def test_prompt_does_not_force_a_tool_for_every_question() -> None:
    """Chốt của người dùng: KHÔNG phải câu nào của Sale cũng phải gọi tool.

    Câu cần số liệu ⇒ bắt buộc gọi tool trước khi kết luận. Câu không cần số liệu (chào hỏi, hỏi cách
    dùng, hỏi định nghĩa/quy trình, góp ý) ⇒ trả lời trực tiếp, không gọi tool cho hình thức.
    """
    prompt = prompts.build_system_prompt(_context_for(REPORTED_QUESTION))

    assert "Không phải câu nào cũng phải gọi tool" in prompt
    assert "BẮT BUỘC gọi tool trước khi kết luận" in prompt
    assert "trả lời trực tiếp" in prompt and "không gọi tool" in prompt
    # Cấm tuyệt đối của bản cũ ("chưa gọi tool thì chưa được kết luận" cho MỌI câu) phải không còn.
    assert "Chưa gọi tool thì chưa được kết luận" not in prompt



def test_system_prompt_carries_unit_and_date_criteria() -> None:
    context = _context_for("Tính phương án cho căn ZEN-A-1205 ngày 2026-10-01 giúp em")
    context["entities"] = {**context["entities"], "transaction_date": "2026-10-01"}
    prompt = prompts.build_system_prompt(context)

    assert "- Mã căn nhắc tới: ZEN-A-1205" in prompt
    assert "- Ngày giao dịch Sale nêu: 2026-10-01" in prompt


def test_plan_is_a_suggestion_not_an_order() -> None:
    prompt = prompts.build_system_prompt(_context_for(REPORTED_QUESTION))
    assert "KẾ HOẠCH GỢI Ý" in prompt
    assert "CHỈ là gợi ý" in prompt
    assert "bạn quyết định" in prompt


def test_question_criteria_omits_empty_fields() -> None:
    """Không nêu gì thì không dựng dòng rác — prompt không bị loãng."""
    assert prompts.question_criteria({}) == []
    assert prompts.question_criteria({"unit_code": "", "amount_vnd": 0}) == []


@pytest.mark.asyncio
async def test_llm_decides_area_filter_and_it_reaches_the_tool() -> None:
    """Model tự gọi tool với tham số diện tích theo câu hỏi ⇒ tool nhận đúng tham số đó.

    Đây là điểm khác biệt cốt lõi so với lớp từ khóa: quyết định gọi gì/tham số nào nằm ở LLM; hệ thống
    chỉ đưa dữ liệu câu hỏi vào prompt và thực thi đúng yêu cầu của model.
    """

    class _AreaAwareLLM:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        def bind_tools(self, tools: list[Any]) -> _AreaAwareLLM:  # noqa: ARG002
            return self

        async def ainvoke(self, messages: list[Any]) -> AIMessage:
            system = str(messages[0].content)
            self.prompts.append(system)
            if "63–77m²" in system and not any(m.__class__.__name__ == "ToolMessage" for m in messages):
                # Lần 1: model đọc tiêu chí trong prompt rồi tự quyết gọi tool với khoảng diện tích.
                return AIMessage(
                    content="Em lọc giỏ theo đúng khoảng diện tích anh/chị nêu.",
                    tool_calls=[
                        {
                            "name": "tra_cuu_gio_hang",
                            "args": {
                                "so_phong_ngu": 0,
                                "gia_toi_da_vnd": 3_000_000_000,
                                "dien_tich_min_m2": 63,
                                "dien_tich_max_m2": 77,
                                "ngay_giao_dich": "2026-09-26",
                            },
                            "id": "call-area",
                        }
                    ],
                )
            return AIMessage(content="Em đã lọc xong giỏ theo khoảng diện tích anh/chị nêu.")

    llm = _AreaAwareLLM()
    events = [(e.type, e.data) async for e in stream_copilot(CopilotRequest(message=REPORTED_QUESTION), llm=llm)]

    assert llm.prompts and "63–77m²" in llm.prompts[0]
    actions = [data for kind, data in events if kind == "action"]
    assert actions and actions[0]["tool"] == "tra_cuu_gio_hang"
    # Tham số do LLM quyết định đi thẳng tới tool, không bị lớp từ khóa thay bằng bộ tham số khác.
    assert actions[0]["args"]["dien_tich_min_m2"] == 63
    assert actions[0]["args"]["dien_tich_max_m2"] == 77

    final = next(data for kind, data in events if kind == "final")
    assert final["mode"] == "react"
    assert "tra_cuu_gio_hang" in final["tools_used"]


def test_criteria_reflect_the_reported_question_numbers() -> None:
    """Chốt lại con số của câu hỏi bị lỗi: 70m² ⇒ 63–77m² (±10%), 3 tỷ ⇒ 3.000.000.000 VNĐ."""
    intent = intents.detect_intent(REPORTED_QUESTION)
    area = intent.entities["area_range_m2"]
    assert area == (63.0, 77.0)
    assert intent.entities["amount_vnd"] == 3_000_000_000
    assert grounding.format_vnd(intent.entities["amount_vnd"]) == "3.000.000.000 ₫"


# ─── Không phải câu nào cũng phải gọi tool ────────────────────────────────────────────────────────
from src.agents.copilot import graph as copilot_graph  # noqa: E402
from src.agents.copilot import intents as copilot_intents  # noqa: E402


class _DirectAnswerIntent:
    """Ý định tối thiểu để gọi `_finalize` trong test."""

    def __init__(self, intent: str) -> None:
        self.intent = intent
        self.entities: dict[str, str] = {}


def test_direct_answer_without_tool_has_no_grounding_warning() -> None:
    """LLM trả lời trực tiếp, KHÔNG gọi tool ⇒ câu trả lời hợp lệ, không gắn cảnh báo "chưa đối chiếu"."""
    final = copilot_graph._finalize(
        "Quy trình bàn giao hồ sơ gồm 3 bước: xác nhận nhu cầu, gửi hồ sơ cho Sale, hẹn lịch tư vấn.",
        [],  # không có observation nào: model không gọi tool
        None,
        [],
        _DirectAnswerIntent(copilot_intents.INTENT_LOOKUP_POLICY),
        question="Quy trình bàn giao hồ sơ khách hàng gồm mấy bước?",
    )
    assert "chưa đối chiếu" not in final["internal_notes"]
    assert final["reply"]


def test_direct_answer_with_invented_number_is_still_flagged() -> None:
    """Ngoại lệ giữ nguyên: tự bịa số mà không gọi tool thì vẫn bị cảnh báo."""
    final = copilot_graph._finalize(
        "Dự án đang chiết khấu 12% cho tất cả các căn.",
        [],
        None,
        [],
        _DirectAnswerIntent(copilot_intents.INTENT_LOOKUP_POLICY),
        question="Chính sách chiết khấu thế nào?",
    )
    assert "chưa đối chiếu" in final["internal_notes"]
