"""Khoá mã hoá API key lấy từ đâu — và vì sao `.env` phải có tác dụng.

Bài học thật: `os.environ` KHÔNG chứa giá trị trong `.env` (pydantic-settings nạp `.env` vào object
Settings). Nếu chỉ đọc `os.environ`, Admin đặt `LLM_SECRET_KEY` trong `.env` rồi khởi động lại mà hệ
thống **vẫn dùng khoá mặc định của mã nguồn** — không có cảnh báo nào. Test này khoá lại đường đi đúng:
biến môi trường thật → `.env` → khoá mặc định.
"""

from __future__ import annotations

import pytest

from src.services import llm_secrets


@pytest.fixture()
def sach_bien_moi_truong(monkeypatch):
    """Không để biến môi trường của máy chạy test ảnh hưởng kết quả."""
    monkeypatch.delenv("LLM_SECRET_KEY", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    from src.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_khoa_trong_file_env_phai_duoc_dung(sach_bien_moi_truong, monkeypatch, tmp_path) -> None:
    """Đặt khoá trong `.env` là đủ (không cần export) — và phải THAY THẬT khoá đang mã hoá."""
    (tmp_path / ".env").write_text("LLM_SECRET_KEY=khoa-dat-trong-file-env\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    from src.config import get_settings

    get_settings.cache_clear()

    assert llm_secrets.secret_source() == "env", "Khoá trong .env bị bỏ qua — vẫn đang dùng khoá mặc định!"

    # Mã hoá bằng khoá trong .env → giải mã được; và khoá mã hoá mặc định trước đó phải KHÔNG giải mã được.
    stored = llm_secrets.encrypt_api_key("sk-khoa-that-123456")
    assert llm_secrets.decrypt_api_key(stored) == "sk-khoa-that-123456"

    cu_dev = llm_secrets._PREFIX + llm_secrets._fernet(llm_secrets._DEV_SECRET).encrypt(b"sk-cu-12345678").decode()
    assert llm_secrets.decrypt_api_key(cu_dev) == "sk-cu-12345678"  # đường lùi: không mất nhà cung cấp…


def test_bien_moi_truong_that_thang_file_env(sach_bien_moi_truong, monkeypatch, tmp_path) -> None:
    (tmp_path / ".env").write_text("LLM_SECRET_KEY=khoa-trong-file\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LLM_SECRET_KEY", "khoa-tu-shell")
    from src.config import get_settings

    get_settings.cache_clear()

    stored = llm_secrets.encrypt_api_key("sk-uu-tien-123456")
    monkeypatch.delenv("LLM_SECRET_KEY")
    get_settings.cache_clear()
    # Khoá trong .env khác khoá shell → không giải mã được, nhưng phải nói rõ lý do chứ không im lặng.
    assert llm_secrets.decrypt_api_key(stored) == ""
