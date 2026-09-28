"""POL-08 Speech Standards & Compliance Rules (C-11 / F8).

Defines prohibited promotional statements, mandatory disclaimers, and
required evidence anchors for real estate sales conversations.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProhibitedPattern(BaseModel):
    """A pattern defining prohibited phrase or promise."""

    pattern_id: str
    regex: str
    category: str = Field(..., description="PROFIT_GUARANTEE, LOAN_GUARANTEE, UNAUTHORIZED_DISCOUNT")
    severity: str = Field("PROHIBITED", description="PROHIBITED or CONDITIONAL")
    description: str


# POL-08 Prohibited patterns
POL_08_PROHIBITED_PATTERNS: list[ProhibitedPattern] = [
    ProhibitedPattern(
        pattern_id="POL08-PROHIBIT-01",
        regex=r"(cam kết|đảm bảo|chắc chắn)\s+(sinh lời|lợi nhuận|lãi suất|hoàn vốn)",
        category="PROFIT_GUARANTEE",
        severity="PROHIBITED",
        description="Nghiêm cấm cam kết tỷ suất lợi nhuận hoặc sinh lời chắc chắn.",
    ),
    ProhibitedPattern(
        pattern_id="POL08-PROHIBIT-02",
        regex=r"(bao|chắc chắn|cam kết)\s+(duyệt|được)\s+(vay|tín dụng|hồ sơ)",
        category="LOAN_GUARANTEE",
        severity="PROHIBITED",
        description="Nghiêm cấm cam kết hoặc bao duyệt khoản vay ngân hàng trái thẩm quyền.",
    ),
    ProhibitedPattern(
        pattern_id="POL08-PROHIBIT-03",
        regex=r"(đầu tư|mua)\s+không\s+(có\s+)?rủi ro",
        category="PROFIT_GUARANTEE",
        severity="PROHIBITED",
        description="Nghiêm cấm tuyên bố dự án hoàn toàn không có rủi ro.",
    ),
    ProhibitedPattern(
        pattern_id="POL08-PROHIBIT-04",
        regex=r"giảm\s+(thêm|riêng)\s+ngoài\s+chính\s+sách",
        category="UNAUTHORIZED_DISCOUNT",
        severity="PROHIBITED",
        description="Nghiêm cấm hứa hẹn chiết khấu vượt thẩm quyền ngoài chính sách ban hành.",
    ),
]

# Mandatory disclaimers when stating financial estimates
MANDATORY_DISCLAIMERS = [
    "chính sách có thể thay đổi",
    "áp dụng theo phê duyệt",
    "theo văn bản chính sách",
]
