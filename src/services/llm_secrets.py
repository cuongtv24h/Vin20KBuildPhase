"""Mã hoá API key của nhà cung cấp LLM trước khi lưu DB.

Admin nhập khoá trên giao diện → khoá **không bao giờ** được trả lại nguyên văn qua API và cũng
không nằm dạng plaintext trong DB. Dùng Fernet (AES-128-CBC + HMAC) với khoá dẫn xuất từ
`LLM_SECRET_KEY` (hoặc `SECRET_KEY`) trong ENV; nếu chưa cấu hình thì dùng khoá phát triển
cố định — đủ để không lộ khoá trong file DB, và tài liệu ghi rõ phải đặt ENV khi lên production.

Vì khoá mã hoá đến từ ENV, khi Admin **đặt `LLM_SECRET_KEY` lần đầu** (hoặc đổi khoá) các khoá API
đã lưu bằng khoá mặc định của mã nguồn sẽ không giải mã được bằng khoá mới. Hàm `decrypt_api_key`
vẫn thử khoá mặc định như đường lùi để **không làm sập dịch vụ**, đồng thời ghi cảnh báo yêu cầu
nhập lại khoá để mã hoá theo khoá mới.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_DEV_SECRET = "vlandfuture-dev-secret-change-me"
_PREFIX = "enc::"


def _settings_secret() -> str:
    """Khoá lấy qua `Settings` — nhờ đó **giá trị trong `.env` cũng có tác dụng**.

    pydantic-settings nạp `.env` vào object Settings chứ không ghi vào `os.environ`, nên nếu chỉ đọc
    `os.environ` thì Admin đặt `LLM_SECRET_KEY` trong `.env` sẽ không được dùng (im lặng!).
    """
    try:
        from src.config import get_settings

        settings = get_settings()
    except Exception:  # noqa: BLE001 — thiếu cấu hình không được làm sập luồng giải mã
        return ""
    return str(getattr(settings, "llm_secret_key", "") or "").strip()


def secret_source() -> str:
    """Nguồn khoá mã hoá đang dùng: `'env'` (an toàn) hay `'dev'` (khoá mặc định của mã nguồn)."""
    return "env" if _secret() != _DEV_SECRET else "dev"


def _secret() -> str:
    # Ưu tiên biến môi trường thật (shell/pm2), sau đó tới `.env`, cuối cùng là khoá mặc định của mã nguồn.
    return os.environ.get("LLM_SECRET_KEY") or os.environ.get("SECRET_KEY") or _settings_secret() or _DEV_SECRET


def _fernet(secret_at_rest: str | None = None) -> Fernet:
    secret = secret_at_rest or _secret()
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_api_key(raw: str) -> str:
    """Mã hoá khoá API; trả chuỗi có tiền tố `enc::` để phân biệt với dữ liệu cũ."""
    if not raw:
        return ""
    if raw.startswith(_PREFIX):
        return raw
    if secret_source() == "dev":
        logger.warning(
            "Đang mã hoá API key bằng khoá mặc định của mã nguồn — hãy đặt `LLM_SECRET_KEY` trong "
            "ENV của máy chủ, rồi nhập lại khoá trong màn hình quản trị để mã hoá theo khoá riêng."
        )
    return _PREFIX + _fernet().encrypt(raw.encode("utf-8")).decode("ascii")


def decrypt_api_key(stored: str) -> str:
    """Giải mã khoá API; dữ liệu chưa mã hoá (bản cũ) trả nguyên trạng để không phá tương thích.

    Nếu khoá được mã hoá bằng khoá mặc định của mã nguồn (Admin vừa đặt `LLM_SECRET_KEY`), vẫn giải
    mã được để không mất nhà cung cấp, kèm cảnh báo phải nhập lại khoá. Không giải mã được bằng cả
    hai khoá (khoá ENV đổi sang giá trị khác) → trả rỗng và cảnh báo.
    """
    if not stored:
        return ""
    if not stored.startswith(_PREFIX):
        return stored
    token = stored[len(_PREFIX) :].encode("ascii")
    try:
        return _fernet().decrypt(token).decode("utf-8")
    except (InvalidToken, ValueError):
        pass
    if _secret() != _DEV_SECRET:
        try:
            raw = _fernet(_DEV_SECRET).decrypt(token).decode("utf-8")
            logger.warning(
                "API key đang được mã hoá bằng khoá mặc định của mã nguồn; đã giải mã tạm để không mất "
                "nhà cung cấp. Hãy nhập lại khoá trong màn hình quản trị để mã hoá theo LLM_SECRET_KEY hiện tại."
            )
            return raw
        except (InvalidToken, ValueError):
            pass
    logger.warning(
        "Không giải mã được API key đã lưu — khoá mã hoá (LLM_SECRET_KEY/SECRET_KEY) đã thay đổi. "
        "Nhập lại API key trong màn hình quản trị để dùng khoá mã hoá mới."
    )
    return ""


def mask_api_key(stored_or_raw: str) -> str:
    """Dạng hiển thị an toàn: `sk-…9f2c`. Không lộ khoá, vẫn đủ để Admin đối chiếu."""
    raw = decrypt_api_key(stored_or_raw) if stored_or_raw.startswith(_PREFIX) else stored_or_raw
    if not raw:
        return ""
    if len(raw) <= 8:
        return "•" * len(raw)
    return f"{raw[:4]}…{raw[-4:]}"
