"""`src/db/dns_patch.py` — fallback DNS Supabase phải bật CÓ ĐIỀU KIỆN và kêu to khi dùng đường dự phòng.

Vì sao có bộ test này: patch đổi `socket.getaddrinfo` của TOÀN tiến trình và từng tự kích hoạt ngay khi
import. Hai rủi ro cần khoá lại bằng test: (1) vá cả khi DB không phải Supabase, (2) âm thầm dùng danh
sách IP tĩnh đã lỗi thời khiến "DB chết không rõ nguyên nhân".
"""

from __future__ import annotations

import logging
import socket

import pytest

from src.db import dns_patch

SUPABASE_URL = "postgresql+asyncpg://u:p@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres"
POOLER_HOST = dns_patch.DEFAULT_SUPABASE_HOST
LOGGER_NAME = "pricepolicy.dns_patch"


@pytest.fixture(autouse=True)
def _restore_socket():
    """Patch là trạng thái toàn tiến trình — test xong phải trả `socket.getaddrinfo` về bản gốc."""
    original = socket.getaddrinfo
    yield
    dns_patch.disable_dns_patch()
    socket.getaddrinfo = original


def _fake_resolver(seen: list[str], blocked_hosts: set[str]):
    """Giả lập resolver: host bị chặn thì gaierror, còn lại (IP) thì trả kết quả."""

    def _resolve(host, port, family=0, type=0, proto=0, flags=0):
        seen.append(str(host))
        if str(host) in blocked_hosts:
            raise socket.gaierror(11001, "getaddrinfo failed")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (str(host), port or 0))]

    return _resolve


def test_khong_va_socket_khi_db_khong_phai_supabase() -> None:
    assert dns_patch.apply_dns_patch("sqlite+aiosqlite:///./data/app.db") is False
    assert dns_patch.is_patched() is False
    assert socket.getaddrinfo is dns_patch._ORIG_GETADDRINFO


def test_va_socket_khi_db_la_supabase() -> None:
    assert dns_patch.apply_dns_patch(SUPABASE_URL) is True
    assert dns_patch.is_patched() is True
    assert socket.getaddrinfo is dns_patch._resilient_getaddrinfo
    # Gọi lần hai không vá chồng.
    assert dns_patch.apply_dns_patch(SUPABASE_URL) is True


def test_dns_he_thong_van_duoc_dung_truoc(monkeypatch) -> None:
    """Đường vui: DNS hệ thống phân giải được thì không đụng DoH/IP tĩnh."""
    dns_patch.apply_dns_patch(SUPABASE_URL)
    seen: list[str] = []
    monkeypatch.setattr(dns_patch, "_ORIG_GETADDRINFO", _fake_resolver(seen, blocked_hosts=set()))
    monkeypatch.setattr(
        dns_patch,
        "_resolve_via_doh",
        lambda host: pytest.fail("Không được gọi DoH khi DNS hệ thống còn sống"),
    )

    result = socket.getaddrinfo(POOLER_HOST, 5432)

    assert result and seen == [POOLER_HOST]


def test_dns_bi_chan_thi_dung_ip_tinh_va_log_canh_bao(monkeypatch, caplog) -> None:
    dns_patch.apply_dns_patch(SUPABASE_URL)
    seen: list[str] = []
    monkeypatch.setattr(dns_patch, "_ORIG_GETADDRINFO", _fake_resolver(seen, blocked_hosts={POOLER_HOST}))
    monkeypatch.setattr(dns_patch, "_resolve_via_doh", lambda host: [])  # DoH cũng bị tường lửa chặn

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        result = socket.getaddrinfo(POOLER_HOST, 5432)

    expected_ip = dns_patch._static_ips()[POOLER_HOST][0]
    assert result, "Phải kết nối được bằng IP tĩnh"
    assert seen == [POOLER_HOST, expected_ip]
    assert POOLER_HOST in caplog.text
    assert expected_ip in caplog.text, "Log phải nêu rõ IP đã dùng để vận hành lần ra IP tĩnh lỗi thời"


def test_env_ghi_de_danh_sach_ip_tinh(monkeypatch) -> None:
    """AWS đổi dải IP: vận hành chỉ cần đặt biến môi trường, không sửa code."""
    dns_patch.apply_dns_patch(SUPABASE_URL)
    monkeypatch.setenv(dns_patch.ENV_STATIC_IPS, "1.1.1.1, 2.2.2.2")
    seen: list[str] = []
    monkeypatch.setattr(dns_patch, "_ORIG_GETADDRINFO", _fake_resolver(seen, blocked_hosts={POOLER_HOST}))
    monkeypatch.setattr(dns_patch, "_resolve_via_doh", lambda host: [])

    socket.getaddrinfo(POOLER_HOST, 5432)

    assert seen == [POOLER_HOST, "1.1.1.1"]


def test_host_khong_phai_supabase_van_bao_loi_dung(monkeypatch) -> None:
    """Không được "cứu" tên miền ngoài Supabase bằng IP tĩnh — sai host là phải báo lỗi."""
    dns_patch.apply_dns_patch(SUPABASE_URL)
    monkeypatch.setattr(
        dns_patch, "_ORIG_GETADDRINFO", _fake_resolver([], blocked_hosts={"khong-ton-tai.example.com"})
    )

    with pytest.raises(socket.gaierror):
        socket.getaddrinfo("khong-ton-tai.example.com", 5432)


def test_disable_tra_socket_ve_ban_goc() -> None:
    dns_patch.apply_dns_patch(SUPABASE_URL)
    dns_patch.disable_dns_patch()
    assert dns_patch.is_patched() is False
    assert socket.getaddrinfo is dns_patch._ORIG_GETADDRINFO
