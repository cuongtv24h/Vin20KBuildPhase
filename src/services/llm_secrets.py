"""Mã hoá API key của nhà cung cấp LLM trước khi lưu DB.

Admin nhập khoá trên giao diện → khoá **không bao giờ** được trả lại nguyên văn qua API và cũng
không nằm dạng plaintext trong DB. Dùng Fernet (AES-128-CBC + HMAC) với khoá dẫn xuất từ
`LLM_SECRET_KEY` (hoặc `SECRET_KEY`) trong ENV; nếu chưa cấu hình thì dùng khoá phát triển
cố định — đủ để không lộ khoá trong file DB, và tài liệu ghi rõ phải đặt ENV khi lên production.
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

_DEV_SECRET = "vlandfuture-dev-secret-change-me"
_PREFIX = "enc::"


def _secret() -> str:
    return os.environ.get("LLM_SECRET_KEY") or os.environ.get("SECRET_KEY") or _DEV_SECRET


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(_secret().encode("utf-8")).digest())
    return Fernet(key)


def encrypt_api_key(raw: str) -> str:
    """Mã hoá khoá API; trả chuỗi có tiền tố `enc::` để phân biệt với dữ liệu cũ."""
    if not raw:
        return ""
    if raw.startswith(_PREFIX):
        return raw
    return _PREFIX + _fernet().encrypt(raw.encode("utf-8")).decode("ascii")


def decrypt_api_key(stored: str) -> str:
    """Giải mã khoá API. Dữ liệu chưa mã hoá (bản cũ) trả nguyên trạng để không phá tương thích."""
    if not stored:
        return ""
    if not stored.startswith(_PREFIX):
        return stored
    try:
        return _fernet().decrypt(stored[len(_PREFIX) :].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


def mask_api_key(stored_or_raw: str) -> str:
    """Dạng hiển thị an toàn: `sk-…9f2c`. Không lộ khoá, vẫn đủ để Admin đối chiếu."""
    raw = decrypt_api_key(stored_or_raw) if stored_or_raw.startswith(_PREFIX) else stored_or_raw
    if not raw:
        return ""
    if len(raw) <= 8:
        return "•" * len(raw)
    return f"{raw[:4]}…{raw[-4:]}"
