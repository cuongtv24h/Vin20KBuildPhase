"""
Resilient DNS Patch for Supabase & External DB Connections.

Giải quyết triệt để lỗi `socket.gaierror [Errno 11001] getaddrinfo failed`
khi mạng nội bộ (Wi-Fi trường học/công ty như VinUni) chặn hoặc timeout
khi phân giải tên miền AWS ELB CNAME của Supabase:
`aws-0-ap-northeast-2.pooler.supabase.com`.

Cơ chế:
1. Thử phân giải qua DNS mặc định của hệ thống trước (không tốn thêm chi phí).
2. Nếu gặp `socket.gaierror`:
   a) Thử phân giải qua Google DNS-over-HTTPS (DoH qua cổng HTTPS 443).
   b) Nếu DoH không khả dụng, dùng danh sách IP tĩnh của AWS Seoul Pooler.
3. Cache kết quả trong bộ nhớ để các truy vấn sau chạy tức thì.
"""

from __future__ import annotations

import json
import logging
import socket
import urllib.request
from typing import Any

logger = logging.getLogger("pricepolicy.dns_patch")

_orig_getaddrinfo = socket.getaddrinfo
_dns_cache: dict[str, list[str]] = {}
_is_patched = False

STATIC_SUPABASE_IPS: dict[str, list[str]] = {
    "aws-0-ap-northeast-2.pooler.supabase.com": [
        "13.124.111.232",
        "15.164.120.176",
        "15.165.245.138",
    ]
}


def _resolve_via_doh(host: str) -> list[str]:
    """Phân giải tên miền qua Google DNS-over-HTTPS (HTTPS/443)."""
    try:
        url = f"https://dns.google/resolve?name={host}&type=A"
        req = urllib.request.Request(url, headers={"User-Agent": "PricePolicy-DNS/1.0"})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            ips = [ans["data"] for ans in data.get("Answer", []) if ans.get("type") == 1 and ans.get("data")]
            if ips:
                return ips
    except Exception as exc:
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
        return _orig_getaddrinfo(host, port, family, type, proto, flags)
    except socket.gaierror:
        if isinstance(host, str) and ("supabase.com" in host or host in STATIC_SUPABASE_IPS):
            if host not in _dns_cache:
                resolved = _resolve_via_doh(host)
                if not resolved:
                    resolved = STATIC_SUPABASE_IPS.get(host, [])
                if resolved:
                    _dns_cache[host] = resolved

            ips = _dns_cache.get(host, [])
            for ip in ips:
                try:
                    return _orig_getaddrinfo(ip, port, family, type, proto, flags)
                except Exception:
                    continue
        raise


def apply_dns_patch() -> None:
    """Kích hoạt patch tự động fallback DNS cho Supabase."""
    global _is_patched
    if not _is_patched:
        socket.getaddrinfo = _resilient_getaddrinfo
        _is_patched = True
        logger.info("[DNS PATCH] Resilient DNS resolver activated for Supabase pooler.")


# Tự động kích hoạt khi import module
apply_dns_patch()
