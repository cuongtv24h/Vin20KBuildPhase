"""
Sales Copilot AI Chat Endpoint.
Provides conversational AI intelligence for Sales Agents in SCR-S00 (Sales Workspace),
grounded in real canonical project data, policies, and FCS pricing rules.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from fastapi import APIRouter, HTTPException, status
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
    action_type: str | None = None  # 'CREATE_CUSTOMER' | 'CREATE_QUOTE' | 'COMPARE_SCENARIOS' | 'SEARCH_UNITS' | 'COMPOSE_MESSAGE'
    action_data: dict[str, Any] | None = None
    suggested_actions: list[str] = Field(default_factory=list)


COPILOT_SYSTEM_PROMPT = """Bạn là Sales Copilot AI - Trợ lý Bán hàng ảo thông minh chuyên trách của hệ thống VLandFuture Riverside (Mã dự án: PROJECT-VLF-001).
Bạn đồng hành trực tiếp cùng các Chuyên viên Kinh doanh (Sale) trong không gian làm việc Sales Agent Workspace (SCR-S00).
Bạn tương tác 100% bằng ngôn ngữ tự nhiên thông minh, chuẩn phong thái chuyên gia tư vấn BĐS cao cấp.

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

### NGUYÊN TẮC GIAO TIẾP VỚI CHUYÊN VIÊN SALE:
1. **Giao tiếp hoàn toàn tự nhiên**:
   - TUYỆT ĐỐI KHÔNG dùng hay gợi ý các câu lệnh dạng gõ dấu gạch chéo (/baogia, /tao-khach, /chinh-sach...) vì hệ thống đã trang bị giao diện Card thông minh và bắt lệnh tự nhiên.
   - Hướng dẫn và phản hồi tự nhiên: "Anh có thể ra lệnh cho em 'Tạo khách hàng mới', 'Lập báo giá căn này', 'So sánh 3 phương án thanh toán' hoặc 'Soạn tin nhắn cho khách'".
2. **Tuân thủ speech guideline F8**: KHÔNG cam kết lợi nhuận đầu tư viển vông, KHÔNG hứa hẹn duyệt vay 100% (tránh vi phạm TIER 4 BLACK).

### TƯƠNG TÁC THẺ THÔNG MINH (INTERACTIVE SMART CARDS):
Khi câu lệnh của chuyên viên Sale thể hiện một trong các ý định sau:
1. Tạo / Thêm khách hàng mới (`smart_customer_create`): ví dụ "tạo khách mới tên Nguyên Văn Quân, sdt 0919992345 Căn hộ lớn hơn 80m, 3 ngủ, tài sản sẵn có 2 tỷ, mong muốn căn đông nam"
2. Tạo / Lập báo giá (`smart_quote_create`): ví dụ "tạo báo giá căn R-02.02 phương án sớm"
3. So sánh phương án thanh toán (`smart_scenario_compare`): ví dụ "so sánh các phương án căn R-02.02"
4. Tra cứu rổ hàng căn hộ (`smart_units_browse`): ví dụ "tra cứu căn hộ trống", "tìm căn 3 ngủ"
5. Soạn tin nhắn tư vấn gửi khách (`smart_compose_message`): ví dụ "soạn tin nhắn tư vấn gửi khách"

BẠN BẮT BUỘC chèn 1 khối JSON ở CUỐI CÙNG câu trả lời theo đúng định dạng sau:
```json:smart_action
{
  "action_type": "smart_customer_create",
  "action_data": {
    "customer_name": "Tên khách hàng đã LỌC SẠCH từ ngữ thừa (ví dụ 'Nguyên Văn Quân', TUYỆT ĐỐI KHÔNG chứa 'tạo khách', 'mới', 'tên', 'anh', 'chị')",
    "customer_phone": "0919992345",
    "preferred_unit_code": "Mã căn phù hợp nhất trong giỏ hàng (nếu khách thích 3 ngủ / >80m2 thì chọn R-05.01, 2 ngủ chọn R-02.02, 1 ngủ chọn R-01.08)",
    "own_funds_vnd": 2000000000,
    "needs_summary": "Tóm tắt nhu cầu cụ thể của khách hàng"
  },
  "suggested_actions": ["Lưu khách hàng vào CRM", "Tạo báo giá căn R-05.01", "So sánh 3 phương án căn R-05.01"]
}
```
(Nếu là câu hỏi thông thường không có ý định hành động nghiệp vụ, không cần chèn khối json:smart_action này).
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
        reply_raw = str(res.content)
    except Exception as exc:
        logger.error(f"Lỗi gọi LLM Copilot: {exc}", exc_info=True)
        reply_raw = (
            f"Chào bạn, em là Sales Copilot VLandFuture. "
            f"Em đã nhận được yêu cầu: \"{user_msg}\". "
            f"Em đang kết nối đến hệ thống tính toán để hỗ trợ bạn lập báo giá và hồ sơ khách hàng."
        )

    # 4. Trích xuất Structured Smart Action Block từ phản hồi của LLM
    action_type = None
    action_data = None
    suggested_actions = ["Tạo báo giá cho căn này", "So sánh 3 phương án thanh toán", "Soạn tin nhắn tư vấn gửi khách"]

    # Tìm khối ```json:smart_action ... ``` hoặc ```json {"action_type": ...} ```
    action_match = re.search(r"```(?:json:smart_action|json)\s*(\{.*?\})\s*```", reply_raw, re.DOTALL)
    if action_match:
        try:
            parsed = json.loads(action_match.group(1))
            action_type = parsed.get("action_type")
            action_data = parsed.get("action_data")
            if parsed.get("suggested_actions"):
                suggested_actions = parsed.get("suggested_actions")
            # Cắt khối json khỏi văn bản hiển thị cho người dùng
            reply_text = re.sub(r"```(?:json:smart_action|json)\s*\{.*?\}\s*```", "", reply_raw, flags=re.DOTALL).strip()
        except Exception as parse_err:
            logger.warning(f"Không thể parse json:smart_action từ LLM: {parse_err}")
            reply_text = reply_raw
    else:
        reply_text = reply_raw

    # Đảm bảo làm sạch họ tên trong action_data nếu có
    if action_data and isinstance(action_data, dict) and "customer_name" in action_data:
        raw_cust_name = str(action_data["customer_name"]).strip()
        cleaned_cust_name = re.sub(
            r"^(?:tạo\s*khách(?:\s*hàng)?(?:\s*mới)?|thêm\s*khách|khách\s*mới|mới\s*tên|mới\s*là|tên\s*là|tên|mới|anh|chị)\s*",
            "",
            raw_cust_name,
            flags=re.IGNORECASE,
        ).strip()
        cleaned_cust_name = re.sub(
            r"[,;:\-]?\s*(?:sđt|sdt|phone|điện\s*thoại|\b0\d{8,10}\b).*$",
            "",
            cleaned_cust_name,
            flags=re.IGNORECASE,
        ).strip()
        if cleaned_cust_name.lower() in ("mới", "khách", "khách hàng", "khách mới", "anh", "chị", "lead", "null", "none"):
            action_data["customer_name"] = ""
        else:
            action_data["customer_name"] = cleaned_cust_name

    # 5. Lớp dự phòng bóc tách nâng cao (Advanced Smart Fallback) nếu LLM chưa kịp chèn JSON
    lower = user_msg.lower()
    if not action_type:
        # Ý định: Tạo khách hàng
        if any(k in lower for k in ("tạo khách", "thêm khách", "khách mới", "nhập khách", "lưu khách", "đăng ký khách", "tạo lead")):
            action_type = "smart_customer_create"
            # Làm sạch họ tên bằng cách loại bỏ triệt để từ thừa
            # Ví dụ: "tạo khách mới tên Nguyên Văn Quân, sdt..." -> "Nguyên Văn Quân"
            clean_name = re.sub(
                r"^(?:tạo\s*khách(?:\s*hàng)?(?:\s*mới)?|thêm\s*khách(?:\s*hàng)?|khách(?:\s*hàng)?\s*mới|đăng\s*ký\s*khách|tạo\s*lead)\s*",
                "",
                user_msg,
                flags=re.IGNORECASE,
            ).strip()
            clean_name = re.sub(
                r"^(?:mới\s+tên|mới\s+là|tên\s+là|tên|mới|anh|chị|khách\s*hàng)\s*",
                "",
                clean_name,
                flags=re.IGNORECASE,
            ).strip()

            phone_match = re.search(r"0\d{9,10}", user_msg)
            phone_in_clean = re.search(r"0\d{9,10}", clean_name)
            if phone_in_clean and phone_in_clean.start() > 0:
                # Nếu có số điện thoại trong clean_name, lấy phần chữ trước số điện thoại
                candidate_name = clean_name[:phone_in_clean.start()].strip()
                candidate_name = re.sub(r"[,;:\-]?\s*(?:sđt|sdt|phone|điện\s*thoại)?\s*$", "", candidate_name, flags=re.IGNORECASE).strip()
                if candidate_name:
                    clean_name = candidate_name
            else:
                clean_name = clean_name.split(",")[0].split(";")[0].strip()

            clean_name = re.sub(r"^(?:mới\s+tên|tên\s+là|tên|mới)\s*", "", clean_name, flags=re.IGNORECASE).strip()

            if not clean_name or len(clean_name) < 2 or clean_name.lower() in ("mới", "khách", "khách hàng", "khách mới", "anh", "chị", "lead"):
                clean_name = ""

            # Bóc tách số điện thoại
            phone = phone_match.group(0) if phone_match else ""

            # Bóc tách tiêu chí căn hộ & map vào rổ hàng
            if any(k in lower for k in ("3 ngủ", "3br", "3 phòng ngủ", "100m", "80m")):
                pref_unit = "R-05.01"
            elif any(k in lower for k in ("1 ngủ", "1br", "studio", "50m")):
                pref_unit = "R-01.08"
            else:
                unit_match = re.search(r"(?:căn|mã|unit)?\s*([A-Za-z0-9]+-[A-Za-z0-9\.]+)", user_msg, re.IGNORECASE)
                pref_unit = unit_match.group(1).upper() if unit_match else (req.current_unit or "R-02.02")

            # Bóc tách vốn tự có / tài sản sẵn có
            funds_match = re.search(r"(\d+(?:[\.,]\d+)?)\s*(tỷ|ty|triệu|tr)", user_msg, re.IGNORECASE)
            funds_val = 1_500_000_000
            if funds_match:
                val = float(funds_match.group(1).replace(",", "."))
                unit_word = funds_match.group(2).lower()
                funds_val = int(val * 1_000_000_000) if unit_word.startswith("t") and not unit_word.startswith("tr") else int(val * 1_000_000)

            action_data = {
                "customer_name": clean_name,
                "customer_phone": phone,
                "preferred_unit_code": pref_unit,
                "own_funds_vnd": funds_val,
                "needs_summary": f"Khách hàng {clean_name} quan tâm căn {pref_unit}. Vốn tự có ~{funds_val:,} VNĐ.",
            }
            suggested_actions = ["Lưu khách hàng vào CRM", f"Tạo báo giá căn {pref_unit}", f"So sánh 3 phương án căn {pref_unit}"]

        # Ý định: Lập báo giá
        elif any(k in lower for k in ("tạo báo giá", "lập báo giá", "tính giá căn", "ra báo giá", "báo giá")):
            action_type = "smart_quote_create"
            unit_match = re.search(r"(?:căn|mã|unit)?\s*([A-Za-z0-9]+-[A-Za-z0-9\.]+)", user_msg, re.IGNORECASE)
            u_code = unit_match.group(1).upper() if unit_match else (req.current_unit or "R-02.02")
            sc = "PA-SOM" if any(w in lower for w in ("sớm", "nhanh", "chiết khấu", "ck")) else ("PA-VAY" if any(w in lower for w in ("vay", "lãi", "ngân hàng")) else "PA-CHUAN")
            action_data = {
                "unit_code": u_code,
                "scenario": sc,
            }
            suggested_actions = ["Trình duyệt báo giá", "So sánh với phương án vay ngân hàng", "Soạn tin nhắn gửi khách"]

        # Ý định: So sánh phương án thanh toán
        elif any(k in lower for k in ("so sánh", "các phương án", "dòng tiền", "phương án nào tốt", "tính dòng tiền")):
            action_type = "smart_scenario_compare"
            unit_match = re.search(r"(?:căn|mã|unit)?\s*([A-Za-z0-9]+-[A-Za-z0-9\.]+)", user_msg, re.IGNORECASE)
            action_data = {
                "unit_code": unit_match.group(1).upper() if unit_match else (req.current_unit or "R-02.02"),
            }
            suggested_actions = ["Chọn phương án PA-SOM 8%", "Chọn phương án PA-VAY 0%", "Lập báo giá chi tiết"]

        # Ý định: Tra cứu căn hộ / giỏ hàng
        elif any(k in lower for k in ("tra cứu căn", "tìm căn", "giỏ hàng", "danh sách căn", "căn 2 ngủ", "căn studio", "căn 1 ngủ", "căn 3 ngủ", "căn hộ trống")):
            action_type = "smart_units_browse"
            action_data = {}
            suggested_actions = ["Xem chi tiết căn R-02.02", "Xem chi tiết căn R-05.01", "Tạo khách hàng quan tâm"]

        # Ý định: Soạn tin nhắn F8
        elif any(k in lower for k in ("soạn tin", "tin nhắn", "nhắn cho khách", "nhắn zalo", "viết tin")):
            action_type = "smart_compose_message"
            action_data = {
                "unit_code": req.current_unit or "R-02.02",
                "draftText": f"Dạ em chào anh/chị, em gửi anh/chị phương án báo giá chuẩn căn {req.current_unit or 'R-02.02'} ạ [2]. Khách hàng thanh toán sớm 95% nhận chiết khấu 8% [1]. Hoặc nếu chọn vay ngân hàng sẽ được hỗ trợ lãi suất 0% trong 24 tháng [4]. Anh/chị xem chi tiết nhé!",
            }
            suggested_actions = ["Sao chép tin nhắn Zalo", "Kiểm tra lại tuân thủ F8", "Lập báo giá đính kèm"]

    # Đảm bảo làm sạch tên khách hàng trong action_data nếu có
    if action_type == "smart_customer_create" and action_data and "customer_name" in action_data:
        c_name = str(action_data["customer_name"]).strip()
        c_name = re.sub(r"^(?:tạo\s*khách(?:\s*hàng)?(?:\s*mới)?|thêm\s*khách|mới|tên\s*(?:là)?|anh|chị|khách\s*hàng)\s*", "", c_name, flags=re.IGNORECASE).strip()
        c_name = re.sub(r"[,;:\-]?\s*(?:sđt|sdt|phone|điện\s*thoại|\b0\d{8,10}\b).*$", "", c_name, flags=re.IGNORECASE).strip()
        if c_name.lower() in ("mới", "khách", "khách hàng", "khách mới", "anh", "chị", "lead", "null", "none"):
            c_name = ""
        action_data["customer_name"] = c_name

    return CopilotChatResponse(
        reply=reply_text,
        action_type=action_type,
        action_data=action_data,
        suggested_actions=suggested_actions,
    )
