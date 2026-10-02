"""Critic vòng 2 — tự phản biện trước khi trả lời (§3.3 P2).

Khác với `verifier` (chỉ kiểm *con số có nằm trong Observation không*), critic soi **lập luận và
cách phát ngôn**: câu trả lời có hứa quá thẩm quyền, có nêu ưu đãi mà thiếu mỏ neo chứng cứ, có
dùng từ ngữ cam kết bị POL-08 cấm, hay có nói "0% lãi suất" mà thiếu khuyến cáo bắt buộc không.

Chủ đích thiết kế:
- **Tất định và rẻ**: chạy bằng luật, không tốn thêm lượt LLM ⇒ không nhân đôi độ trễ.
- **Chỉ chạy ở lượt "quan trọng"** (có số tiền, có ưu đãi, hoặc là câu soạn tin/tuân thủ).
- **Không tự sửa lời của LLM**: critic trả về danh sách vấn đề + gợi ý, tầng gọi quyết định
  (mặc định: chèn lời nhắc an toàn, có thể bật một lượt sửa bằng `COPILOT_CRITIC=1`).
- **Chỉ nhắc điều làm được**: yêu cầu "gắn mỏ neo [n]" chỉ đặt ra khi lượt đó **có** citation để trỏ tới;
  lượt tra cứu trả rỗng mà bị nhắc mỏ neo chỉ tạo nhiễu.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

#: Câu trả lời có số tiền → đáng bị soi (Sale có thể dùng nguyên văn gửi khách).
_MONEY_RE = re.compile(r"\d[\d.,]*\s*(?:tỷ|tỉ|triệu|tr\b|vnd|đồng)", re.IGNORECASE)
#: Mỏ neo chứng cứ: [1], [CSBH-ZEN-2026-V3.1 · Điều 4], [FCS v2.6] hoặc POL-...
#: (câu trả lời của Copilot trích nguồn bằng mã văn bản trong ngoặc vuông, không chỉ số thứ tự)
_ANCHOR_RE = re.compile(r"\[\d+\]|\[[A-Z][A-Z0-9._-]{1,}|POL-[A-Z0-9-]+")
#: Đoạn trích nguyên văn trong ngoặc kép — không tính là "Copilot tự nói ra ưu đãi".
_QUOTED_RE = re.compile(r'"[^"]{0,400}"|“[^”]{0,400}”')
#: Cụm từ hứa quá thẩm quyền (trùng tinh thần POL-08 nhưng ở mức cảnh báo, không chặn cứng).
_OVER_PROMISE_RE = re.compile(
    r"(cam kết|bảo đảm|chắc chắn)[^.]{0,40}(duyệt|vay|lãi|sinh lời|sinh lợi|giá|giảm)",
    re.IGNORECASE,
)
#: Ưu đãi có điều kiện: nói "0%", "chiết khấu" mà không nêu điều kiện/khuyến cáo.
_CONDITIONAL_OFFER_RE = re.compile(r"(lãi suất\s*0%|0%\s*(?:trong|cho)|chiết khấu\s*\d+(?:[.,]\d+)?\s*%)", re.IGNORECASE)
_CONDITION_HINT_RE = re.compile(
    r"(điều kiện|nếu|khi|sau \d+ tháng|trong \d+ tháng|trong vòng \d+|kể từ|tối đa|"
    r"theo văn bản|theo quy định|khuyến cáo|tham khảo)",
    re.IGNORECASE,
)


#: Dấu hiệu câu trả lời chứa bảng so sánh do engine tất định sinh ra.
_ENGINE_OUTPUT_RE = re.compile(r"Kết quả engine tất định|khả thi:\s*(?:có|không)|Sanity", re.IGNORECASE)


def _strip_quoted(text: str) -> str:
    """Bỏ các đoạn trích nguyên văn: critic chỉ soi lời Copilot tự nói, không soi văn bản chính sách."""
    return _QUOTED_RE.sub(" ", text)


@dataclass
class Critique:
    """Kết quả tự phản biện."""

    ok: bool = True
    issues: list[dict[str, str]] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "issues": self.issues, "hints": self.hints}


def is_high_stakes(reply: str, intent: str | None = None) -> bool:
    """Lượt trả lời có đáng soi kỹ không (tối ưu chi phí: bỏ qua câu chào hỏi, tra cứu đơn giản)."""
    if str(intent or "") in {"smart_compose_message", "smart_quote_create", "smart_scenario_compare", "f8_check"}:
        return True
    return bool(_MONEY_RE.search(reply) or _CONDITIONAL_OFFER_RE.search(reply))


def _has_anchorable_evidence(observations: list[dict[str, Any]] | None) -> bool:
    """Có chứng cứ nào để gắn mỏ neo không.

    `MONEY_WITHOUT_ANCHOR` chỉ có nghĩa khi **tồn tại** nguồn để trỏ tới. Một lượt tra giỏ hàng trả về
    rỗng (0 citation) mà vẫn nhắc "gắn mỏ neo [n] cho từng con số" là lời nhắc **không hành động được**:
    Sale không có gì để gắn, chỉ thấy câu trả lời bị gắn cờ oan.
    """
    if observations is None:
        # Không truyền observation (dùng như hàm thuần) → giữ luật chặt như trước để tương thích ngược.
        return True
    return any((obs.get("citations") or []) for obs in observations)


def critique_reply(reply: str, *, intent: str | None = None, observations: list[dict[str, Any]] | None = None) -> Critique:
    """Soi câu trả lời bằng luật; trả về danh sách vấn đề kèm gợi ý sửa."""
    text = str(reply or "")
    result = Critique()
    if not text.strip():
        return result

    if _has_anchorable_evidence(observations) and _MONEY_RE.search(text) and not _ANCHOR_RE.search(text):
        result.ok = False
        result.issues.append(
            {
                "code": "MONEY_WITHOUT_ANCHOR",
                "detail": "Có số tiền nhưng không kèm mỏ neo chứng cứ [n]",
            }
        )
        result.hints.append("Gắn mỏ neo [n] cho từng con số trước khi Sale gửi khách.")

    said_by_agent = _strip_quoted(text)

    over = _OVER_PROMISE_RE.search(said_by_agent)
    if over:
        result.ok = False
        result.issues.append(
            {
                "code": "OVER_PROMISE",
                "detail": f"Cụm hứa quá thẩm quyền: “{over.group(0).strip()}”",
            }
        )
        result.hints.append("Đổi sang cách nói có điều kiện: “hồ sơ sẽ được ngân hàng thẩm định theo quy trình”.")

    # Bảng so sánh do engine tất định sinh (có "khả thi: có/không" cho từng phương án) đã tự
    # mang điều kiện của nó — không tính là Copilot nói ưu đãi thiếu điều kiện.
    offer = None if _ENGINE_OUTPUT_RE.search(text) else _CONDITIONAL_OFFER_RE.search(said_by_agent)
    if offer and not _CONDITION_HINT_RE.search(text):
        result.ok = False
        result.issues.append(
            {
                "code": "OFFER_WITHOUT_CONDITION",
                "detail": f"Ưu đãi nêu thiếu điều kiện/khuyến cáo: “{offer.group(0).strip()}”",
            }
        )
        result.hints.append("Nêu rõ điều kiện áp dụng (thời hạn, số tiền, đối tượng) để tránh hiểu sai.")

    return result


def revision_note(critique: Critique) -> str:
    """Câu nhắc an toàn chèn cuối câu trả lời khi critic phát hiện vấn đề."""
    if critique.ok or not critique.hints:
        return ""
    return "\n\n_Kiểm duyệt nội bộ: " + " ".join(critique.hints[:2]) + "_"


def critic_enabled_for_llm_revision() -> bool:
    """Bật một lượt LLM sửa lời (tốn thêm độ trễ) — mặc định TẮT."""
    return os.getenv("COPILOT_CRITIC", "").strip().lower() in {"1", "true", "yes"}
