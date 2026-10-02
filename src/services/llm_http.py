"""Header HTTP dùng chung cho **mọi** lời gọi nhà cung cấp LLM (nút Test kết nối và client thật).

Vì sao cần dùng chung: nút Test kết nối phải kiểm tra đúng đường mà ứng dụng thật đi. Nếu probe gửi
một kiểu header còn Copilot gửi kiểu khác thì kết quả test vô nghĩa — test xanh mà chat đỏ (hoặc ngược lại).

Hai chế độ:

* ``app`` (mặc định): khai báo rõ mình là ứng dụng nào kèm nơi liên hệ. Qua được bộ lọc "chặn client
  không khai báo" nhưng **không** qua được Cloudflare challenge (bot protection) — đúng như thực tế gặp
  với nhà cung cấp đứng sau Cloudflare.
* ``browser``: gửi thêm bộ header mà trình duyệt thật gửi (``User-Agent: Mozilla/5.0 …`` là thứ Cloudflare
  dò trước tiên). Vẫn **không giấu danh tính**: giữ ``X-Client-App`` và đuôi ``P096-VLandFuture`` trong UA.
  Chỉ bật khi nhà cung cấp thực sự đòi — bật bằng ``LLM_HTTP_HEADERS=browser``.

Danh sách này cố ý tối giản và không bao gồm ``Authorization``: khoá API do tầng client tự gắn.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx

#: Tên ứng dụng — cũng là phần nhận diện trong cả hai chế độ header.
APP_USER_AGENT = "P096-VLandFuture-Healthcheck/1.0 (+https://demoday.work.gd)"

#: UA kiểu trình duyệt, giữ đuôi nhận diện ứng dụng để không "giả dạng" hoàn toàn.
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36 P096-VLandFuture/1.0"
)

CLIENT_APP_HEADER = "X-Client-App"
CLIENT_APP_VALUE = "PricePolicy-P096"

#: Thời gian nhớ IP công khai của máy chủ (giây) — tránh gọi dịch vụ ngoài mỗi lần test.
_PUBLIC_IP_TTL = 600.0
_public_ip_cache: tuple[float, str] | None = None


def headers_mode() -> str:
    """Chế độ header đang dùng: ``'app'`` (mặc định) hoặc ``'browser'``.

    Biến môi trường thật (``LLM_HTTP_HEADERS``) thắng giá trị trong ``.env`` — giống cách
    ``llm_secrets`` lấy khoá, để test và vận hành dễ đoán.
    """
    raw = (os.environ.get("LLM_HTTP_HEADERS") or "").strip().lower()
    if not raw:
        try:
            from src.config import get_settings

            raw = str(getattr(get_settings(), "llm_http_headers", "") or "").strip().lower()
        except Exception:  # noqa: BLE001 — thiếu cấu hình không được làm hỏng luồng gọi LLM
            raw = ""
    return "browser" if raw == "browser" else "app"


def other_mode(mode: str) -> str:
    """Chế độ còn lại — dùng để chẩn đoán khi bị chặn."""
    return "app" if mode == "browser" else "browser"


def build_headers(api_key: str | None = None, *, mode: str | None = None, json_body: bool = False) -> dict[str, str]:
    """Bộ header cho một lời gọi nhà cung cấp LLM.

    ``api_key=None`` ⇒ không gắn ``Authorization`` (dùng cho client LangChain — khoá do SDK tự gắn).
    """
    active = mode or headers_mode()
    headers = {
        "User-Agent": BROWSER_USER_AGENT if active == "browser" else APP_USER_AGENT,
        "Accept": "application/json, text/plain, */*" if active == "browser" else "application/json",
        CLIENT_APP_HEADER: CLIENT_APP_VALUE,
    }
    if active == "browser":
        headers["Accept-Language"] = "vi-VN,vi;q=0.9,en;q=0.8"
    if json_body:
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


async def public_ip() -> str:
    """IP công khai mà máy chủ này dùng để ra Internet (best-effort, có cache).

    Cần khi phải nhờ nhà cung cấp allowlist IP — thay vì bắt Admin tự đi tra. Đặt sẵn
    ``LLM_PUBLIC_IP`` trong ENV thì dùng luôn giá trị đó (không gọi dịch vụ ngoài).
    """
    override = (os.environ.get("LLM_PUBLIC_IP") or "").strip()
    if override:
        return override

    global _public_ip_cache
    now = time.monotonic()
    if _public_ip_cache and now - _public_ip_cache[0] < _PUBLIC_IP_TTL:
        return _public_ip_cache[1]

    for url, parse in (
        ("https://api.ipify.org?format=json", _parse_ipify),
        ("https://ifconfig.me/ip", _parse_plain),
    ):
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(url, headers={"User-Agent": APP_USER_AGENT})
            value = parse(response) if response.status_code == 200 else ""
        except Exception:  # noqa: BLE001 — tra IP là bước phụ, hỏng thì bỏ qua
            value = ""
        if value:
            _public_ip_cache = (now, value)
            return value
    return ""


def _parse_ipify(response: Any) -> str:
    return str(json.loads(response.text).get("ip") or "").strip()


def _parse_plain(response: Any) -> str:
    return response.text.strip()
