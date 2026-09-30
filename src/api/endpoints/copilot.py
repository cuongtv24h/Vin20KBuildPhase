"""
Sales Copilot AI Chat Endpoint.
Provides conversational AI intelligence for Sales Agents in SCR-S00 (Sales Workspace),
grounded in real canonical project data, policies, and FCS pricing rules.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.api.endpoints.catalog import PROJECTS_DATA, UNITS_DATA
from src.services.llm import get_llm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/copilot", tags=["copilot"])


class ChatMessageItem(BaseModel):
    role: str = Field(..., description="'user' | 'assistant' | 'agent'")
    content: str


class CopilotChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Nội dung câu hỏi của Sale")
    history: list[ChatMessageItem] = Field(default_factory=list, description="Lịch sử hội thoại gần nhất")
    current_unit: str | None = Field(None, description="Mã căn đang xem nếu có")
    lead_dossier_id: str | None = Field(None, description="Mã hồ sơ khách hàng đang xem nếu có")


class CopilotChatResponse(BaseModel):
    reply: str
    suggested_action: str | None = None
    suggested_command: str | None = None


COPILOT_SYSTEM_PROMPT = """Bạn là Sales Copilot AI - Trợ lý Bán hàng ảo thông minh hàng đầu của hệ thống VLandFuture Riverside (Mã dự án: PROJECT-VLF-001).
Bạn đồng hành trực tiếp cùng các Chuyên viên Kinh doanh (Sale) trong không gian làm việc Sales Agent Workspace (SCR-S00).

### THÔNG TIN DỰ ÁN & GIỎ HÀNG:
- Dự án: VLand Future Riverside (Văn Giang, Hưng Yên) - 40 căn hộ cao cấp (Studio, 1BR, 2BR, 3BR, Penthouse).
- Giá niêm yết: từ ~2.08 tỷ (Studio 32m²) đến ~14.7 tỷ (Penthouse).
- Căn hộ 2 phòng ngủ tiêu chuẩn: diện tích ~68m² - 75m², giá niêm yết từ 4.2 tỷ - 5.5 tỷ.

### CHÍNH SÁCH BÁN HÀNG HIỆN HÀNH (POL-2026-EARLY):
1. Phương án PA-NHANH (Thanh toán sớm 95% bằng vốn tự có):
   - Chiết khấu thanh toán sớm: 8.0% trên giá bán trước thuế.
   - Thích hợp nhất cho khách hàng có sẵn dòng tiền lớn (Objective: MIN_NET_PRICE).
2. Phương án PA-VAY (Hỗ trợ lãi suất ngân hàng):
   - Hỗ trợ lãi suất 0% trong 24 tháng theo chính sách POL-2026-VLF-BANK.
   - Vốn tự có ban đầu chỉ cần 20% - 30%, ngân hàng giải ngân đến 70%.
   - Thích hợp cho khách hàng muốn tối ưu dòng tiền ban đầu (Objective: MIN_INITIAL_OUTFLOW).
3. Phương án PA-TIENDO (Thanh toán theo tiến độ chuẩn):
   - Chia làm 8-10 đợt linh hoạt theo tiến độ xây dựng.
4. Quà tặng & Khuyến mãi:
   - Gói nội thất cao cấp trị giá 200.000.000 VNĐ (POL-2026-VLF-FURNITURE).
   - Miễn phí quản lý dịch vụ 2 năm đầu.

### NGUYÊN TẮC HOẠT ĐỘNG & BẢO VỆ PHÁP LÝ (F8 Compliance):
- Luôn trả lời tự nhiên, thân thiện, súc tích, chuyên nghiệp và có chiều sâu nghiệp vụ bất động sản.
- Khi người dùng chào hỏi ("Xin Chào", "Hi", "Hello"), hãy chào lại nồng nhiệt, xưng là Sales Copilot của VLandFuture, và giới thiệu ngắn gọn các việc bạn có thể trợ giúp đắc lực (tra cứu căn, giải thích chính sách, lập báo giá, hướng dẫn lệnh /slash).
- Tuân thủ speech guideline F8: KHÔNG cam kết lợi nhuận đầu tư viển vông, KHÔNG hứa hẹn pháp lý sai lệch (tránh TIER 4 BLACK).
- Gợi ý cho Sale các thao tác lệnh tắt hữu ích khi phù hợp:
  + `/tao-khach [Tên, SĐT, Căn, Vốn]` để tạo hồ sơ khách nhanh vào CRM.
  + `/tim-khach` để tìm hồ sơ khách hàng.
  + `/baogia` để mở pipeline báo giá.
  + `/chinh-sach` để mở danh mục chính sách bán hàng.
  + `/soan-tin` để mở khung soạn tin F8 kiểm tra tuân thủ.
"""


@router.post("/chat", response_model=CopilotChatResponse)
async def copilot_chat(req: CopilotChatRequest) -> CopilotChatResponse:
    """Chat với Sales Copilot sử dụng LLM thật (Groq Qwen / Fallbacks)."""
    user_msg = req.message.strip()
    if not user_msg:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tin nhắn không được để trống.",
        )

    # 1. Chuẩn bị ngữ cảnh bổ sung nếu có
    context_notes = []
    if req.current_unit:
        unit = next((u for u in UNITS_DATA if u["unit_code"] == req.current_unit), None)
        if unit:
            context_notes.append(
                f"[Ngữ cảnh hiện tại: Sale đang chọn căn {unit['unit_code']} - Loại: {unit['unit_type']}, "
                f"Diện tích: {unit['net_area_m2']}m², Giá niêm yết trước thuế: {unit['listed_price_before_tax_vnd']:,} VNĐ]"
            )
    if req.lead_dossier_id:
        context_notes.append(f"[Sale đang mở hồ sơ khách hàng: {req.lead_dossier_id}]")

    sys_content = COPILOT_SYSTEM_PROMPT
    if context_notes:
        sys_content += "\n\n" + "\n".join(context_notes)

    # 2. Xây dựng prompt messages
    messages = [SystemMessage(content=sys_content)]
    for h in req.history[-6:]:
        if h.role in ("user", "human"):
            messages.append(HumanMessage(content=h.content))
        elif h.role in ("assistant", "agent"):
            messages.append(AIMessage(content=h.content))

    messages.append(HumanMessage(content=user_msg))

    # 3. Gọi LLM
    try:
        llm = get_llm()
        res = await llm.ainvoke(messages)
        reply_text = str(res.content)
    except Exception as exc:
        logger.error(f"Lỗi gọi LLM Copilot: {exc}", exc_info=True)
        # Fallback thông minh nếu LLM gặp sự cố
        reply_text = (
            f"Chào bạn, em là Sales Copilot VLandFuture. "
            f"Em đã nhận được yêu cầu: \"{user_msg}\". "
            f"Hiện tại em có thể hỗ trợ bạn tra cứu giỏ hàng 40 căn hộ tại Riverside, "
            f"tính toán phương án thanh toán sớm 95% (chiết khấu 8%) hoặc gói hỗ trợ lãi suất 0% 24 tháng. "
            f"Bạn có thể dùng các lệnh nhanh như `/tao-khach`, `/tim-khach`, hoặc `/baogia` nhé!"
        )

    # Phát hiện gợi ý lệnh
    suggested_cmd = None
    if any(k in user_msg.lower() for k in ("tạo khách", "thêm khách", "khách mới")):
        suggested_cmd = "/tao-khach"
    elif any(k in user_msg.lower() for k in ("tìm khách", "tra cứu khách")):
        suggested_cmd = "/tim-khach"
    elif any(k in user_msg.lower() for k in ("báo giá", "tính giá", "lập giá")):
        suggested_cmd = "/baogia"
    elif any(k in user_msg.lower() for k in ("chính sách", "chiết khấu", "ưu đãi")):
        suggested_cmd = "/chinh-sach"

    return CopilotChatResponse(
        reply=reply_text,
        suggested_command=suggested_cmd,
    )
