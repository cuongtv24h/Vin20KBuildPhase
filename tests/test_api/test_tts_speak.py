"""Đọc câu trả lời thành tiếng qua nhà cung cấp TTS (`POST /tts/speak`) — bước kế tiếp của §7.

Bộ test khoá lại những điều dễ sai và dễ tốn tiền oan:

- Nhà cung cấp trình duyệt **không** gửi qua backend (0 đồng); chưa đủ điều kiện (thiếu Base URL/khoá) thì
  nói thẳng việc cần làm, không giả vờ đọc được.
- **Không có danh sách mã cứng**: nhà cung cấp bất kỳ do quản trị viên tự thêm vẫn đọc được; nhà cung cấp
  chọn trước mà lỗi thì **tự chuyển sang nhà cung cấp kế tiếp** (đúng cơ chế dự phòng của nhà cung cấp LLM).
- Thiếu khoá ⇒ câu lỗi đọc được, hướng dẫn nhập ở đâu.
- **Che PII** (SĐT/email khách) và **cắt theo hạn mức ký tự** trước khi văn bản rời khỏi hệ thống.
- **Cache**: đọc lại cùng câu không gọi nhà cung cấp lần hai (không tốn thêm tiền) nhưng vẫn trả audio.
- **Ghi chi phí** vào `llm_usage.jsonl` với `kind = "tts"` + số ký tự, để tab “Chi phí & hiệu năng”
  cộng đúng và hạn mức ngày chặn được lúc vượt trần.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient

from src.api.deps import create_access_token

SALE_HEADERS = {"Authorization": f"Bearer {create_access_token('nam.hoang@vlandfuture.vn', 'SALE')}"}
ADMIN_HEADERS = {"Authorization": f"Bearer {create_access_token('admin@vlandfuture.vn', 'ADMIN')}"}

#: WAV 1 giây im lặng (đủ để giả lập audio trả về; nội dung không quan trọng với test).
FAKE_AUDIO = b"RIFF$\x00\x00\x00WAVEfmt " + b"\x00" * 24


class _TtsHandler(BaseHTTPRequestHandler):
    """Server giả cho `POST /audio/speech` — ghi lại thân yêu cầu để test kiểm chứng."""

    requests: list[dict] = []
    status = 200

    def log_message(self, *args: object) -> None:  # pragma: no cover — tắt log ồn ào
        return

    def do_POST(self) -> None:  # noqa: N802 — tên do BaseHTTPRequestHandler quy định
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8", "replace")
        try:
            body = json.loads(raw or "{}")
        except json.JSONDecodeError:
            body = {"_raw": raw}
        type(self).requests.append(
            {
                "path": self.path,
                "auth": self.headers.get("Authorization", ""),
                "body": body,
            }
        )
        if type(self).status != 200:
            self.send_response(type(self).status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": {"message": "bad key"}}')
            return
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.end_headers()
        self.wfile.write(FAKE_AUDIO)


@pytest_asyncio.fixture
async def bad_tts_server(monkeypatch, tmp_path):
    """Server trả 404 JSON — mô phỏng nhà cung cấp **không** dùng giao thức OpenAI-compatible."""
    handler = type("BadHandler", (_TtsHandler,), {"requests": [], "status": 404})
    server = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield handler, f"http://127.0.0.1:{server.server_port}/v1"
    server.shutdown()
    server.server_close()


@pytest_asyncio.fixture
async def tts_server(monkeypatch, tmp_path):
    """Server TTS giả + cache/hạn mức riêng cho từng test (không đụng đĩa thật)."""
    handler = type("Handler", (_TtsHandler,), {"requests": [], "status": 200})
    server = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base_url = f"http://127.0.0.1:{server.server_port}/v1"

    monkeypatch.setenv("TTS_CACHE_DIR", str(tmp_path / "tts_cache"))
    monkeypatch.setenv("LLM_USAGE_PATH", str(tmp_path / "llm_usage.jsonl"))
    monkeypatch.delenv("TTS_DAILY_CHAR_BUDGET", raising=False)

    from sqlalchemy import delete

    from src.db.models import TTSProviderModel, TTSSettingsModel
    from src.services import tts_providers
    from tests.conftest import async_test_session_factory

    async with async_test_session_factory() as session:
        # Cả thiết lập giọng đọc: test trước có thể đã đặt `max_chars_per_turn` nhỏ để kiểm cắt chữ.
        await session.execute(delete(TTSProviderModel))
        await session.execute(delete(TTSSettingsModel))
        await session.commit()
    tts_providers.set_tts_provider_rows(None)

    from src.config import get_settings

    get_settings.cache_clear()
    yield handler, base_url
    server.shutdown()
    server.server_close()
    tts_providers.set_tts_provider_rows(None)
    get_settings.cache_clear()


async def _register(client: AsyncClient, base_url: str, *, api_key: str = "sk-tts-1234567890", price: float = 15.0):
    """Khai báo nhà cung cấp OpenAI TTS trỏ về server giả (đúng luồng quản trị đợt 22)."""
    payload = {
        "provider": "openai",
        "label": "OpenAI TTS (server giả)",
        "mode": "api",
        "base_url": base_url,
        "default_model": "tts-1",
        "env_key": "OPENAI_API_KEY",
        "price_per_1m_chars": price,
        "currency": "USD",
        "price_note": "giá thử",
        "verified_at": "2026-10-03",
        "note": "",
        "voices_text": "alloy | Alloy — trung tính | neutral",
        "supports_streaming": True,
        "voice_cloning": False,
        "api_key": api_key,
        "priority": 1,
        "is_active": True,
    }
    res = await client.post("/api/v1/admin/tts/providers", json=payload, headers=ADMIN_HEADERS)
    assert res.status_code == 201, res.text
    return res.json()


async def _set_provider(client: AsyncClient, provider: str, voice: str = "alloy") -> None:
    # Chỉ ADMIN/MANAGER đổi được mặc định dùng chung — dùng tài khoản ADMIN cho gọn.
    res = await client.put(
        "/api/v1/settings/tts",
        json={"scope": "default", "provider": provider, "voice": voice},
        headers=ADMIN_HEADERS,
    )
    assert res.status_code == 200, res.text


class TestDuongDoc:
    @pytest.mark.asyncio
    async def test_trinh_duyet_khong_gui_qua_backend(self, client: AsyncClient, tts_server):
        handler, _url = tts_server
        await _set_provider(client, "browser", voice="vi-VN")
        res = await client.post("/api/v1/tts/speak", json={"text": "Xin chào"}, headers=SALE_HEADERS)
        assert res.status_code == 409
        assert "trình duyệt" in res.json()["detail"]
        assert handler.requests == [], "không được gọi mạng khi đọc bằng giọng máy"

    @pytest.mark.asyncio
    async def test_chua_co_nha_cung_cap_nao_goi_duoc_thi_noi_ro_thieu_gi(self, client: AsyncClient, tts_server):
        """Không nhà cung cấp nào đủ điều kiện (chưa có khoá) ⇒ 503 kèm việc cần làm, không gọi mạng."""
        handler, _url = tts_server
        await _set_provider(client, "viettel", voice="hn_female_ngochuyen")
        res = await client.post("/api/v1/tts/speak", json={"text": "Xin chào"}, headers=SALE_HEADERS)
        assert res.status_code == 503
        assert "Base URL + khoá" in res.json()["detail"]
        assert handler.requests == []

    @pytest.mark.asyncio
    async def test_moi_nha_cung_cap_co_base_url_la_goi_duoc_khong_can_danh_sach_cung(
        self, client: AsyncClient, tts_server
    ):
        """Mã nhà cung cấp bất kỳ (không có trong danh mục dựng sẵn) vẫn đọc được — đúng yêu cầu."""
        handler, base_url = tts_server
        payload = {
            "provider": "cong-ty-tts-abc",
            "label": "Nhà cung cấp của công ty",
            "mode": "api",
            "base_url": base_url,
            "default_model": "model-x",
            "price_per_1m_chars": 1000,
            "currency": "VND",
            "voices_text": "giong-01 | Giọng công ty | female",
            "api_key": "tok-abc-9999",
            "priority": 1,
            "is_active": True,
        }
        assert (await client.post("/api/v1/admin/tts/providers", json=payload, headers=ADMIN_HEADERS)).status_code == 201
        await _set_provider(client, "cong-ty-tts-abc", voice="giong-01")

        res = await client.post("/api/v1/tts/speak", json={"text": "Xin chào"}, headers=SALE_HEADERS)
        assert res.status_code == 200, res.text
        assert res.json()["provider"] == "cong-ty-tts-abc"
        assert handler.requests[0]["path"] == "/v1/audio/speech"
        assert handler.requests[0]["auth"] == "Bearer tok-abc-9999"

    @pytest.mark.asyncio
    async def test_nha_cung_cap_loi_thi_tu_chuyen_sang_nha_cung_cap_ke_tiep(
        self, client: AsyncClient, tts_server, bad_tts_server
    ):
        """Sao chép cơ chế dự phòng của LLM: nhà cung cấp ưu tiên lỗi thì tự chuyển tiếp, có ghi log."""
        good_handler, good_url = tts_server
        _bad_handler, bad_url = bad_tts_server
        # Ưu tiên (priority 1) là nhà cung cấp KHÔNG dùng giao thức OpenAI-compatible ⇒ sẽ lỗi.
        first = {
            "provider": "nha-cung-cap-cu",
            "label": "Nhà cung cấp cũ",
            "mode": "api",
            "base_url": bad_url,
            "default_model": "cu-v1",
            "price_per_1m_chars": 10,
            "currency": "USD",
            "voices_text": "giong-cu | Giọng cũ | female",
            "api_key": "tok-cu-0001",
            "priority": 1,
            "is_active": True,
        }
        second = {
            "provider": "nha-cung-cap-moi",
            "label": "Nhà cung cấp mới",
            "mode": "api",
            "base_url": good_url,
            "default_model": "moi-v1",
            "price_per_1m_chars": 5,
            "currency": "USD",
            "voices_text": "giong-moi | Giọng mới | female",
            "api_key": "tok-moi-0002",
            "priority": 2,
            "is_active": True,
        }
        for payload in (first, second):
            assert (await client.post("/api/v1/admin/tts/providers", json=payload, headers=ADMIN_HEADERS)).status_code == 201
        await _set_provider(client, "nha-cung-cap-cu", voice="giong-cu")

        res = await client.post("/api/v1/tts/speak", json={"text": "Xin chào"}, headers=SALE_HEADERS)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["provider"] == "nha-cung-cap-moi", "phải tự chuyển sang nhà cung cấp kế tiếp"
        assert body["fallback_used"] is True
        assert [a["provider"] for a in body["attempts"]] == ["nha-cung-cap-cu", "nha-cung-cap-moi"]
        assert body["attempts"][0]["ok"] is False and body["attempts"][1]["ok"] is True
        # Giọng của nhà cung cấp dự phòng được dùng (mã giọng của nhà cung cấp cũ là mã lạ với họ).
        assert body["voice"] == "giong-moi"
        assert good_handler.requests[0]["body"]["voice"] == "giong-moi"

        # Nhật ký ghi cả lượt lỗi lẫn lượt thành công (kèm cờ chuyển tiếp) để tab chi phí thấy đúng.
        import os

        usage_path = Path(os.environ["LLM_USAGE_PATH"])
        records = [json.loads(line) for line in usage_path.read_text(encoding="utf-8").strip().splitlines()]
        assert [r["provider"] for r in records] == ["nha-cung-cap-cu", "nha-cung-cap-moi"]
        assert records[0]["ok"] is False and records[0]["error"] == "PROVIDER_ERROR"
        assert records[1]["ok"] is True and records[1]["is_fallback"] is True

    @pytest.mark.asyncio
    async def test_het_chuoi_thi_502_kem_ly_do_va_goi_y_base_url(
        self, client: AsyncClient, tts_server, bad_tts_server
    ):
        """Cả chuỗi đều lỗi ⇒ 502 nêu lý do từng nhà cung cấp; nhà cung cấp trả 404 được nhắc gợi ý Base URL."""
        _handler, bad_url = bad_tts_server
        payload = {
            "provider": "tts-api-rieng",
            "label": "TTS API riêng",
            "mode": "api",
            "base_url": bad_url,
            "default_model": "v1",
            "price_per_1m_chars": 10,
            "currency": "USD",
            "voices_text": "giong-01 | Giọng 01 | female",
            "api_key": "tok-404-0001",
            "priority": 1,
            "is_active": True,
        }
        assert (await client.post("/api/v1/admin/tts/providers", json=payload, headers=ADMIN_HEADERS)).status_code == 201
        await _set_provider(client, "tts-api-rieng")

        res = await client.post("/api/v1/tts/speak", json={"text": "Xin chào"}, headers=SALE_HEADERS)
        assert res.status_code == 502
        detail = res.json()["detail"]
        assert "TTS API riêng" in detail and "404" in detail
        assert "/v1" in detail, "phải gợi ý Base URL theo giao thức OpenAI-compatible"

    @pytest.mark.asyncio
    async def test_chua_dang_nhap_thi_khong_doc_duoc(self, client: AsyncClient, tts_server):
        res = await client.post("/api/v1/tts/speak", json={"text": "Xin chào"})
        assert res.status_code == 401


class TestGoiNhaCungCapThat:
    @pytest.mark.asyncio
    async def test_doc_thanh_cong_va_tra_du_so_lieu(self, client: AsyncClient, tts_server):
        handler, base_url = tts_server
        await _register(client, base_url)
        await _set_provider(client, "openai", voice="alloy")

        await client.put(
            "/api/v1/settings/tts",
            json={"scope": "default", "provider": "openai", "voice": "alloy", "model": "tts-1"},
            headers=ADMIN_HEADERS,
        )
        res = await client.post("/api/v1/tts/speak", json={"text": "Dạ, căn ZEN-A-1205 còn hàng."}, headers=SALE_HEADERS)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["provider"] == "openai" and body["voice"] == "alloy"
        assert body["mime"] == "audio/mpeg"
        assert body["cached"] is False
        import base64

        assert base64.b64decode(body["audio_base64"]) == FAKE_AUDIO
        assert body["chars"] > 0 and body["cost"] > 0 and body["currency"] == "USD"
        assert body["latency_ms"] >= 0

        # Nhà cung cấp nhận đúng nội dung + khoá Bearer.
        assert len(handler.requests) == 1
        sent = handler.requests[0]
        assert sent["path"] == "/v1/audio/speech"
        assert sent["auth"] == "Bearer sk-tts-1234567890"
        assert sent["body"]["model"] == "tts-1" and sent["body"]["voice"] == "alloy"
        assert "ZEN-A-1205" in sent["body"]["input"]

    @pytest.mark.asyncio
    async def test_che_pii_va_cat_theo_han_muc_truoc_khi_gui_di(self, client: AsyncClient, tts_server):
        handler, base_url = tts_server
        await _register(client, base_url)
        await _set_provider(client, "openai")
        await client.put(
            "/api/v1/settings/tts",
            json={"scope": "default", "max_chars_per_turn": 80},
            headers=ADMIN_HEADERS,
        )

        text = "Gọi khách 0912345678 hoặc email khach@vland.vn rồi báo giá căn ZEN-A-1205 cho họ ngay."
        res = await client.post("/api/v1/tts/speak", json={"text": text}, headers=SALE_HEADERS)
        assert res.status_code == 200, res.text
        sent_text = handler.requests[0]["body"]["input"]
        assert "0912345678" not in sent_text and "khach@vland.vn" not in sent_text
        assert "091***78" in sent_text and "***@***" in sent_text
        assert len(sent_text) <= 80, "cắt theo hạn mức ký tự mỗi lượt đọc"
        assert res.json()["chars"] == len(sent_text)

    @pytest.mark.asyncio
    async def test_cache_khong_goi_lai_nha_cung_cap(self, client: AsyncClient, tts_server):
        handler, base_url = tts_server
        await _register(client, base_url)
        await _set_provider(client, "openai")

        first = await client.post("/api/v1/tts/speak", json={"text": "Xin chào anh/chị."}, headers=SALE_HEADERS)
        second = await client.post("/api/v1/tts/speak", json={"text": "Xin chào anh/chị."}, headers=SALE_HEADERS)
        assert first.json()["cached"] is False
        assert second.json()["cached"] is True
        assert len(handler.requests) == 1, "đọc lại cùng câu không được gọi nhà cung cấp lần hai"
        import base64

        assert base64.b64decode(second.json()["audio_base64"]) == FAKE_AUDIO

    @pytest.mark.asyncio
    async def test_ghi_chi_phi_kieu_tts_de_tab_chi_phi_cong_dung(self, client: AsyncClient, tts_server, tmp_path):
        _handler, base_url = tts_server
        await _register(client, base_url, price=4.0)
        await _set_provider(client, "openai")

        res = await client.post("/api/v1/tts/speak", json={"text": "A" * 500}, headers=SALE_HEADERS)
        assert res.status_code == 200
        lines = (tmp_path / "llm_usage.jsonl").read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["kind"] == "tts"
        assert record["chars"] == 500
        assert record["input_tokens"] == 0 and record["output_tokens"] == 0
        assert record["cost"] == pytest.approx(500 / 1_000_000 * 4.0, abs=1e-9)

        summary = await client.get("/api/v1/admin/llm/usage/summary", headers=ADMIN_HEADERS)
        body = summary.json()
        assert body["tts_calls"] == 1 and body["tts_chars"] == 500
        assert body["total_cost"] > 0

    @pytest.mark.asyncio
    async def test_vuot_han_muc_ngay_thi_chan_truoc_khi_goi(self, client: AsyncClient, tts_server, monkeypatch):
        handler, base_url = tts_server
        await _register(client, base_url)
        await _set_provider(client, "openai")

        from src.config import get_settings

        monkeypatch.setenv("TTS_DAILY_CHAR_BUDGET", "20")
        get_settings.cache_clear()

        res = await client.post("/api/v1/tts/speak", json={"text": "X" * 100}, headers=SALE_HEADERS)
        assert res.status_code == 402
        assert "Hạn mức đọc thành tiếng hôm nay" in res.json()["detail"]
        assert handler.requests == [], "vượt hạn mức thì không được gọi nhà cung cấp (không tốn tiền)"

        quota = await client.get("/api/v1/tts/quota", headers=SALE_HEADERS)
        assert quota.json()["daily_budget"] == 20
        assert quota.json()["remaining"] == 20

    @pytest.mark.asyncio
    async def test_chi_doc_ban_tom_tat_khi_bat_ranh_tay(self, client: AsyncClient, tts_server):
        handler, base_url = tts_server
        await _register(client, base_url)
        await _set_provider(client, "openai")

        long_text = "Câu một về căn hộ. " * 40
        res = await client.post(
            "/api/v1/tts/speak", json={"text": long_text, "summary_only": True}, headers=SALE_HEADERS
        )
        assert res.status_code == 200
        sent = handler.requests[0]["body"]["input"]
        assert len(sent) <= 240 and sent.startswith("Câu một về căn hộ.")

    @pytest.mark.asyncio
    async def test_nha_cung_cap_tu_them_kieu_openai_compatible(self, client: AsyncClient, tts_server):
        """Máy chủ tự dựng (ví dụ VieNeu-TTS) cũng đọc được nếu nói giao thức OpenAI-compatible."""
        handler, base_url = tts_server
        payload = {
            "provider": "vieneu",
            "label": "VieNeu TTS (tự dựng)",
            "mode": "api",
            "base_url": base_url,
            "default_model": "vieneu-v3",
            "env_key": "VIENEU_TTS_TOKEN",
            "price_per_1m_chars": 0,
            "currency": "VND",
            "voices_text": "vi-female-01 | Nữ miền Bắc | female",
            "api_key": "tok-vieneu-1234",
            "priority": 5,
            "is_active": True,
        }
        created = await client.post("/api/v1/admin/tts/providers", json=payload, headers=ADMIN_HEADERS)
        assert created.status_code == 201, created.text
        await _set_provider(client, "vieneu", voice="vi-female-01")

        res = await client.post("/api/v1/tts/speak", json={"text": "Xin chào"}, headers=SALE_HEADERS)
        assert res.status_code == 200, res.text
        assert res.json()["provider"] == "vieneu"
        assert handler.requests[0]["auth"] == "Bearer tok-vieneu-1234"
