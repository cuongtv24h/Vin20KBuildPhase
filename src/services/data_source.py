"""Cờ chọn nguồn dữ liệu: CSDL thật (mặc định) hay fixture canonical (chỉ khi bật rõ ràng).

Bối cảnh: sản phẩm chạy online **chỉ** được đọc dữ liệu thật từ PostgreSQL. Fixture canonical
(`POLICIES_DATA` / `UNITS_DATA` trong `src/api/endpoints/catalog.py`) chỉ còn là dữ liệu cho test và
cho môi trường demo offline; muốn dùng phải bật `ALLOW_FIXTURE_DATA=1`, mặc định TẮT.

Vì sao đọc `os.environ` ngay lúc gọi (chứ không qua `get_settings()` đã cache): test cần bật/tắt cờ
theo từng ca, còn tiến trình thật thì biến môi trường được nạp từ `.env` lúc khởi động và không đổi.
"""

from __future__ import annotations

import os

#: Tên biến môi trường — xem `.env.example`.
FIXTURE_ENV = "ALLOW_FIXTURE_DATA"

_TRUE = {"1", "true", "yes", "on"}


def fixtures_allowed() -> bool:
    """`True` chỉ khi người vận hành bật cờ fixture; mặc định là **không** (chỉ dùng CSDL)."""
    return os.environ.get(FIXTURE_ENV, "").strip().lower() in _TRUE


__all__ = ["FIXTURE_ENV", "fixtures_allowed"]
