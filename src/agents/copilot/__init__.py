"""Sales Copilot ReAct Agent (SCR-S00).

Vòng lặp ReAct (Thought → Action → Observation) có công cụ thật:
- Tra cứu chính sách (PEC-RAG time-travel, fallback fixture canonical)
- Tra cứu giỏ hàng căn hộ
- Tính phương án thanh toán tất định (PricingClient, Decimal 28)
- Kiểm tra tuân thủ phát ngôn F8 / POL-08
- Tra cứu hồ sơ khách hàng (Lead Dossier)
- Soạn tin tư vấn + tự kiểm F8

Mọi khẳng định về chính sách/giá/dòng tiền phải bắt nguồn từ Observation của tool
(citation bắt buộc) — không suy đoán từ trí nhớ của LLM.
"""

from src.agents.copilot.graph import CopilotEvent, stream_copilot
from src.agents.copilot.service import CopilotService

__all__ = ["CopilotEvent", "CopilotService", "stream_copilot"]
