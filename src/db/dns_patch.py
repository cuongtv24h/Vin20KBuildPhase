"""Fallback DNS cho Supabase pooler khi mạng nội bộ chặn phân giải tên miền.

Giải quyết lỗi `socket.gaierror [Errno 11001] getaddrinfo failed` khi mạng Wi-Fi trường học/công ty
(như VinUni) chặn hoặc timeout lúc phân giải CNAME AWS ELB của Supabase, ví dụ
`aws-0-ap-northeast-2.pooler.supabase.com`.

Cơ chế:
1. Thử phân giải bằng DNS mặc định của hệ thống trước (không tốn chi phí).
2. Nếu gặp `socket.gaierror` và host là Supabase:
   a. Thử DNS-over-HTTPS của Google (443).
   b. DoH cũng chết thì dùng danh sách IP tĩnh — có thể ghi đè bằng `DB_DNS_STATIC_IPS` để vận hành
      cập nhật khi AWS đổi IP mà không phải sửa code.
3. Cache kết quả trong bộ nhớ.

Hai điểm kỷ luật (từng là rủi ro khi module tự vá lúc import):
- **Bật có điều kiện**: patch đổi `socket.getaddrinfo` của TOÀN tiến trình, nên chỉ kích hoạt khi
  `DB_DNS_FALLBACK=true` (mặc định true) VÀ `DATABASE_URL` thực sự trỏ tới Supabase. Chạy DB nơi khác
  (SQLite/Postgres nội bộ) thì không vá gì cả.
- **Kêu to khi phải dùng đường dự phòng**: log WARNING nêu rõ host và IP đã dùng, để IP tĩnh hết hạn
  không âm thầm trở thành "DB chết không rõ nguyên nhân".
"""

from __future__ import annotations

import json
import logging
import os
import socket
import urllib.request
from typing import Any

logger = logging.getLogger("pricepolicy.dns_patch")

#: Hàm gốc của hệ thống — giữ lại để khôi phục (`disable_dns_patch`) và để so sánh trong test.
_ORIG_GETADDRINFO = socket.getaddrinfo

_dns_cache: dict[str, list[str]] = {}
_is_patched = False

DEFAULT_SUPABASE_HOST = "aws-0-ap-northeast-2.pooler.supabase.com"

#: IP dự phòng khi cả DNS hệ thống lẫn DoH đều không phân giải được. AWS có thể đổi dải IP: ghi đè bằng
#: `DB_DNS_STATIC_IPS=1.2.3.4,5.6.7.8` (và `DB_DNS_STATIC_HOST=<host>` nếu pooler đổi tên).
STATIC_SUPABASE_IPS: dict[str, list[str]] = {
    DEFAULT_SUPABASE_HOST: [
        "13.124.111.232",
        "15.164.120.176",
        "15.165.245.138",
    ]
}

ENV_STATIC_IPS = "DB_DNS_STATIC_IPS"
ENV_STATIC_HOST = "DB_DNS_STATIC_HOST"


def _static_ips() -> dict[str, list[str]]:
    """Danh sách IP tĩnh đang hiệu lực (env ghi đè mặc định)."""
    table = {host: list(ips) for host, ips in STATIC_SUPABASE_IPS.items()}
    raw = os.getenv(ENV_STATIC_IPS, "").strip()
    if not raw:
        return table
    host = os.getenv(ENV_STATIC_HOST, DEFAULT_SUPABASE_HOST).strip() or DEFAULT_SUPABASE_HOST
    ips = [ip.strip() for ip in raw.split(",") if ip.strip()]
    if ips:
        table[host] = ips
    return table


def _is_supabase_host(host: Any) -> bool:
    return isinstance(host, str) and ("supabase.com" in host or "supabase.co" in host)


def _resolve_via_doh(host: str) -> list[str]:
    """Phân giải tên miền qua Google DNS-over-HTTPS (HTTPS/443 — thường không bị tường lửa nội bộ chặn)."""
    try:
        url = f"https://dns.google/resolve?name={host}&type=A"
        req = urllib.request.Request(url, headers={"User-Agent": "PricePolicy-DNS/1.0"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            ips = [ans["data"] for ans in data.get("Answer", []) if ans.get("type") == 1 and ans.get("data")]
            if ips:
                return ips
    except Exception as exc:  # noqa: BLE001 — mạng nội bộ chặn thì bỏ qua, xuống IP tĩnh
        logger.debug("DoH lookup failed for %s: %s", host, exc)
    return []


def _resilient_getaddrinfo(
    host: Any,
    port: Any,
    family: int = 0,
    type: int = 0,
    proto: int = 0,
    flags: int = 0,
) -> list[tuple[Any, Any, Any, Any, Any]]:
    try:
        return _ORIG_GETADDRINFO(host, port, family, type, proto, flags)
    except socket.gaierror:
        if not _is_supabase_host(host):
            raise
        if host not in _dns_cache:
            resolved = _resolve_via_doh(str(host))
            source = "DNS-over-HTTPS"
            if not resolved:
                resolved = _static_ips().get(str(host), [])
                source = "IP tĩnh (DB_DNS_STATIC_IPS)"
            if resolved:
                _dns_cache[str(host)] = resolved
                logger.warning(
                    "[DNS PATCH] %s không phân giải được qua DNS hệ thống — dùng %s: %s. "
                    "Nếu IP tĩnh đã lỗi thời, đặt %s để cập nhật mà không cần sửa code.",
                    host,
                    source,
                    ", ".join(resolved),
                    ENV_STATIC_IPS,
                )

        for ip in _dns_cache.get(str(host), []):
            try:
                return _ORIG_GETADDRINFO(ip, port, family, type, proto, flags)
            except Exception:  # noqa: BLE001 — thử IP kế tiếp
                continue
        raise


def apply_dns_patch(database_url: str | None = None) -> bool:
    """Kích hoạt fallback DNS. Trả về `True` nếu thực sự vá `socket.getaddrinfo`.

    Chỉ vá khi URL DB trỏ tới Supabase: không có lý do gì đổi hàm phân giải tên miền của cả tiến trình
    khi host không thuộc nhóm bị chặn.
    """
    global _is_patched
    if _is_patched:
        return True
    if "supabase" not in (database_url or "").lower():
        logger.debug("[DNS PATCH] DATABASE_URL không trỏ tới Supabase — không vá socket.getaddrinfo.")
        return False
    socket.getaddrinfo = _resilient_getaddrinfo
    _is_patched = True
    logger.info("[DNS PATCH] Đã bật fallback DNS cho Supabase pooler (tắt bằng DB_DNS_FALLBACK=false).")
    return True


def disable_dns_patch() -> None:
    """Trả `socket.getaddrinfo` về bản gốc và xoá cache — dùng cho test/dev, không dùng lúc đang chạy."""
    global _is_patched
    if _is_patched:
        socket.getaddrinfo = _ORIG_GETADDRINFO
        _is_patched = False
    _dns_cache.clear()


def is_patched() -> bool:
    """Trạng thái hiện tại — `/copilot/health` và test dùng để báo cáo."""
    return _is_patched
