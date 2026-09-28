"""Guardrail Security Scanners (N-02 / N-14A / C-11).

Provides input prompt injection scanning and output leakage detection
as specified in CodeBaseIndex.md Section 4.2 and Workflow Design TD-4.3.
"""

from __future__ import annotations

import re
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class GuardrailScanResult(BaseModel):
    """Result of a security scan."""

    is_safe: bool = Field(..., description="Whether the scanned text is safe")
    risk_level: Literal["SAFE", "LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(..., description="Assessed risk level")
    violations: list[str] = Field(default_factory=list, description="Descriptions of violations found")
    detected_patterns: list[str] = Field(default_factory=list, description="Specific matched pattern names")


# Known prompt injection & jailbreak patterns (Input Guardrail N-02)
_INJECTION_PATTERNS: list[tuple[str, str, str]] = [
    # (Regex pattern, Name, Description)
    (
        r"(ignore|disregard|forget)\s+((all|previous|prior|above)\s+)*(instructions|prompts|rules|commands)",
        "INSTRUCTION_OVERRIDE_EN",
        "Attempts to override system instructions (English)",
    ),
    (
        r"(bỏ qua|hủy bỏ|quên(\s+đi)?|xóa)\s+((toàn bộ|tất cả|mọi|hết|các)\s+)*(hướng dẫn|chỉ thị|quy tắc|câu lệnh)",
        "INSTRUCTION_OVERRIDE_VI",
        "Cố tình ghi đè hoặc vô hiệu hóa chỉ thị hệ thống (Tiếng Việt)",
    ),
    (
        r"(act\s+as|pretend\s+to\s+be|you\s+are\s+now)\s+(DAN|unrestricted|jailbreak|hacker|root|admin)",
        "JAILBREAK_ROLEPLAY",
        "Attempts to induce roleplay bypassing safety guardrails",
    ),
    (
        r"(đóng vai|hãy là|bây giờ bạn là)\s+(hacker|admin|người không bị giới hạn|kẻ xấu)",
        "JAILBREAK_ROLEPLAY_VI",
        "Đóng vai nhằm phá vỡ giới hạn an toàn",
    ),
    (
        r"(reveal|show|print|display|dump)\s+(the\s+)?(system\s+prompt|developer\s+instructions|hidden\s+rules)",
        "PROMPT_EXTRACTION_EN",
        "Attempts to extract system prompt or confidential developer instructions",
    ),
    (
        r"(tiết lộ|hiển thị|in ra|cho xem|đọc)\s+((toàn bộ|tất cả|mọi|nội dung)\s+)*(system\s+prompt|prompt(\s+nội\s+bộ)?|hướng dẫn hệ thống|chỉ thị ngầm|quy tắc nội bộ)",
        "PROMPT_EXTRACTION_VI",
        "Yêu cầu tiết lộ system prompt hoặc chỉ thị ngầm của hệ thống",
    ),
    (
        r"(<\|im_start\|>|<\|im_end\|>|\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>|---BEGIN SYSTEM---)",
        "DELIMITER_INJECTION",
        "Attempts to inject special tokens or system delimiters",
    ),
    (
        r"(\bUNION\s+SELECT\b|\bDROP\s+TABLE\b|;\s*SHUTDOWN\b|'\s*OR\s*'1'\s*=\s*'1)",
        "SQLI_PATTERN",
        "Potential SQL injection pattern in user input notes",
    ),
]


# Known output leakage & unauthorized commitment patterns (Output Guardrail N-14A)
_LEAKAGE_PATTERNS: list[tuple[str, str, str]] = [
    (
        r"(sk-[a-zA-Z0-9]{20,}|bearer\s+[a-zA-Z0-9_\-\.]{20,}|api[_\-\s]?key\s*[:=]\s*[a-zA-Z0-9]+)",
        "CREDENTIAL_LEAKAGE",
        "Detected API key, bearer token, or secret credentials in output",
    ),
    (
        r"(hướng dẫn hệ thống của tôi là|my system prompt is|as an ai language model instructed to)",
        "SYSTEM_PROMPT_LEAKAGE",
        "Output discloses internal system prompt or meta-instructions",
    ),
    (
        r"(cam kết\s+(chắc chắn\s+)?(sinh lời|lãi suất|hoàn tiền\s+100%|không rủi ro|duyệt vay\s+100%))",
        "ILLEGAL_COMMITMENT_VI",
        "Cam kết trái luật về lợi nhuận tuyệt đối hoặc duyệt vay không điều kiện",
    ),
    (
        r"(hứa hẹn|đảm bảo tuyệt đối)\s+(ngân hàng sẽ duyệt|không cần chứng minh thu nhập|lợi nhuận tối thiểu)",
        "UNAUTHORIZED_GUARANTEE_VI",
        "Hứa hẹn vượt thẩm quyền ngoài chính sách ban hành",
    ),
    (
        r"(biên\s+lợi\s+nhuận\s+nội\s+bộ|chiết\s+khấu\s+ngầm\s+cho\s+lãnh\s+đạo|giá\s+vốn\s+nội\s+bộ)",
        "INTERNAL_MARGIN_LEAKAGE",
        "Tiết lộ thông tin mật về biên lợi nhuận hoặc giá vốn nội bộ",
    ),
]


def scan_prompt_injection(prompt: str) -> GuardrailScanResult:
    """Scans input prompt for jailbreak, prompt injection, or system override attempts (N-02)."""
    if not prompt or not prompt.strip():
        return GuardrailScanResult(is_safe=True, risk_level="SAFE")

    violations: list[str] = []
    detected: list[str] = []

    for pattern, name, desc in _INJECTION_PATTERNS:
        if re.search(pattern, prompt, re.IGNORECASE):
            violations.append(desc)
            detected.append(name)

    if not violations:
        return GuardrailScanResult(is_safe=True, risk_level="SAFE")

    # Determine risk level
    if any(k in detected for k in ["DELIMITER_INJECTION", "JAILBREAK_ROLEPLAY", "INSTRUCTION_OVERRIDE_VI"]):
        risk = "CRITICAL"
    else:
        risk = "HIGH"

    return GuardrailScanResult(
        is_safe=False,
        risk_level=risk,
        violations=violations,
        detected_patterns=detected,
    )


def scan_output_leakage(text: str) -> GuardrailScanResult:
    """Scans generated output for secret credentials, prompt leakage, or illegal commitments (N-14A)."""
    if not text or not text.strip():
        return GuardrailScanResult(is_safe=True, risk_level="SAFE")

    violations: list[str] = []
    detected: list[str] = []

    for pattern, name, desc in _LEAKAGE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            violations.append(desc)
            detected.append(name)

    if not violations:
        return GuardrailScanResult(is_safe=True, risk_level="SAFE")

    if any(k in detected for k in ["CREDENTIAL_LEAKAGE", "INTERNAL_MARGIN_LEAKAGE"]):
        risk = "CRITICAL"
    else:
        risk = "HIGH"

    return GuardrailScanResult(
        is_safe=False,
        risk_level=risk,
        violations=violations,
        detected_patterns=detected,
    )


@tool
def check_prompt_safety(prompt: str) -> str:
    """Kiểm tra an toàn đầu vào chống prompt injection và jailbreak (N-02).

    Args:
        prompt: Văn bản câu hỏi hoặc ghi chú cần kiểm tra.

    Returns:
        Chuỗi thông báo trạng thái an toàn hoặc vi phạm.
    """
    res = scan_prompt_injection(prompt)
    if res.is_safe:
        return "SAFE: Đầu vào an toàn, không phát hiện dấu hiệu tấn công hoặc can thiệp chỉ thị."
    return f"BLOCKED: Phát hiện rủi ro [{res.risk_level}]. Vi phạm: {', '.join(res.violations)}."


@tool
def check_output_safety(text: str) -> str:
    """Kiểm tra an toàn đầu ra chống rò rỉ thông tin mật và cam kết trái luật (N-14A).

    Args:
        text: Văn bản giải trình hoặc tin nhắn do AI sinh ra.

    Returns:
        Chuỗi thông báo trạng thái an toàn hoặc vi phạm.
    """
    res = scan_output_leakage(text)
    if res.is_safe:
        return "SAFE: Đầu ra an toàn, không có rò rỉ dữ liệu hoặc cam kết ngoài chính sách."
    return f"BLOCKED: Phát hiện rủi ro [{res.risk_level}]. Vi phạm: {', '.join(res.violations)}."


__all__ = [
    "GuardrailScanResult",
    "scan_prompt_injection",
    "scan_output_leakage",
    "check_prompt_safety",
    "check_output_safety",
]
