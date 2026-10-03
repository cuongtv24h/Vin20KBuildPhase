"""Quản trị nhà cung cấp TTS: dùng lại cơ chế khoá của LLM + cho phép thêm nhà cung cấp mới (đợt 22).

Người dùng yêu cầu: *“Dùng sẵn cơ chế cũ đã có, cho phép thêm mới nhà cung cấp ngoài các nhà cung cấp sẵn.”*

Bộ test khoá lại đúng những điều dễ sai:

- chỉ ADMIN vào được (khoá API là tài sản hạ tầng);
- **khoá không bao giờ trả nguyên văn** — chỉ dạng che `sk-…abcd`;
- thêm được **nhà cung cấp mới hoàn toàn** (ngoài danh mục) và nó xuất hiện ở thiết lập giọng đọc;
- tạo được **bản ghi đè** cho nhà cung cấp dựng sẵn (nhập khoá, sửa đơn giá) mà không phá danh mục;
- thứ tự ưu tiên khoá **DB → ENV** (DB thắng, và xoá bản ghi thì quay lại ENV);
- nút **Test kết nối** nói đúng sự thật: chưa có khoá ⇒ `NOT_CONFIGURED`, sai khoá ⇒ `ERROR`, server giả
  OpenAI-compatible ⇒ `OK`; nhà cung cấp không mở endpoint kiểm tra ⇒ `UNSUPPORTED` kèm cách kiểm tay.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient

from src.api.deps import create_access_token
from src.services import tts_providers

ADMIN_HEADERS = {"Authorization": f"Bearer {create_access_token('admin@vlandfuture.vn', 'ADMIN')}"}
SALE_HEADERS = {"Authorization": f"Bearer {create_access_token('nam.hoang@vlandfuture.vn', 'SALE')}"}

CUSTOM_PAYLOAD = {
    "provider": "vieneu",
    "label": "VieNeu TTS (self-host)",
    "mode": "api",
    "base_url": "http://10.0.0.5:8080",
    "default_model": "vieneu-v3",
    "env_key": "VIENEU_TTS_TOKEN",
    "price_per_1m_chars": 0,
    "currency": "VND",
    "price_note": "Tự host — chi phí cố định theo máy, không tính theo ký tự.",
    "verified_at": "2026-10-03",
    "note": "Chạy trong mạng nội bộ, dữ liệu không ra ngoài.",
    "voices_text": "vi-female-01 | Nữ miền Bắc | female\nvi-male-01 | Nam miền Bắc | male",
    "api_key": "tok-vieneu-1234",
}


@pytest_asyncio.fixture(autouse=True)
async def clean_tts_state():
    """Bảng `tts_providers` dùng chung engine in-memory giữa các test ⇒ phải tự dọn."""
    from sqlalchemy import delete

    from src.db.models import TTSProviderModel, TTSSettingsModel
    from tests.conftest import async_test_session_factory

    tts_providers.set_tts_provider_rows(None)
    yield
    async with async_test_session_factory() as session:
        await session.execute(delete(TTSProviderModel))
        # Thiết lập giọng đọc cũng phải dọn: một ca lưu lựa chọn cho nhà cung cấp tự thêm sẽ làm ca sau
        # (đã xoá nhà cung cấp đó) rơi vào nhánh "nhà cung cấp không còn".
        await session.execute(delete(TTSSettingsModel))
        await session.commit()
    tts_providers.set_tts_provider_rows(None)


async def _create(client: AsyncClient, payload: dict) -> dict:
    res = await client.post("/api/v1/admin/tts/providers", json=payload, headers=ADMIN_HEADERS)
    assert res.status_code == 201, res.text
    return res.json()


class TestPhanQuyen:
    @pytest.mark.asyncio
    async def test_sale_khong_duoc_xem(self, client: AsyncClient):
        res = await client.get("/api/v1/admin/tts/providers", headers=SALE_HEADERS)
        assert res.status_code == 403

    @pytest.mark.asyncio
    async def test_sale_khong_duoc_them(self, client: AsyncClient):
        res = await client.post("/api/v1/admin/tts/providers", json=CUSTOM_PAYLOAD, headers=SALE_HEADERS)
        assert res.status_code == 403

    @pytest.mark.asyncio
    async def test_chua_dang_nhap_bi_chan(self, client: AsyncClient):
        # Cùng quy ước với `/admin/llm/providers`: thiếu phiên đăng nhập cũng trả 403 (không tiết lộ
        # endpoint có tồn tại hay không).
        res = await client.get("/api/v1/admin/tts/providers")
        assert res.status_code == 403


class TestDanhMuc:
    @pytest.mark.asyncio
    async def test_gom_nha_cung_cap_dung_san(self, client: AsyncClient):
        res = await client.get("/api/v1/admin/tts/providers", headers=ADMIN_HEADERS)
        assert res.status_code == 200
        data = res.json()
        items = {item["provider"]: item for item in data["items"]}
        assert {"browser", "openai", "google_cloud", "azure", "viettel", "vbee", "fpt"} <= set(items)
        assert data["source"] == "builtin"
        # Trình duyệt: sẵn sàng, không cần khoá, không phải bản ghi DB.
        assert items["browser"]["api_key_configured"] is True
        assert items["browser"]["key_source"] == "browser"
        assert items["browser"]["custom"] is False and items["browser"]["has_db_row"] is False

    @pytest.mark.asyncio
    async def test_them_nha_cung_cap_moi_ngoai_danh_muc(self, client: AsyncClient):
        created = await _create(client, CUSTOM_PAYLOAD)
        assert created["provider"] == "vieneu"
        assert created["custom"] is True and created["has_db_row"] is True
        assert created["api_key_configured"] is True and created["key_source"] == "db"
        assert created["voices"] == [
            {"code": "vi-female-01", "label": "Nữ miền Bắc", "gender": "female"},
            {"code": "vi-male-01", "label": "Nam miền Bắc", "gender": "male"},
        ]
        assert created["api_key_masked"].endswith("1234") and "tok-vieneu-1234" not in str(created)

        listing = (await client.get("/api/v1/admin/tts/providers", headers=ADMIN_HEADERS)).json()
        codes = [item["provider"] for item in listing["items"]]
        assert codes[-1] == "vieneu", "nhà cung cấp mới nằm cuối danh sách"
        assert listing["source"] == "db"

    @pytest.mark.asyncio
    async def test_nha_cung_cap_moi_hien_o_thiet_lap_giong_doc(self, client: AsyncClient):
        """Thêm xong là dùng được ngay — không phải khởi động lại backend."""
        await _create(client, CUSTOM_PAYLOAD)
        res = await client.get("/api/v1/settings/tts", headers=SALE_HEADERS)
        assert res.status_code == 200
        catalog = {item["provider"]: item for item in res.json()["catalog"]}
        assert "vieneu" in catalog
        assert catalog["vieneu"]["api_key_configured"] is True
        assert catalog["vieneu"]["custom"] is True
        assert catalog["vieneu"]["voices"][0]["code"] == "vi-female-01"

        # Và lưu được lựa chọn dùng nhà cung cấp đó ngay (không bị coi là "không hợp lệ").
        res = await client.put(
            "/api/v1/settings/tts",
            json={"scope": "default", "provider": "vieneu", "voice": "vi-female-01"},
            headers=ADMIN_HEADERS,
        )
        assert res.status_code == 200, res.text
        assert res.json()["effective"]["provider"] == "vieneu"

    @pytest.mark.asyncio
    async def test_db_loi_thi_trang_giong_doc_van_chay(self, client: AsyncClient, monkeypatch):
        """Bảng `tts_providers` chưa kịp tạo ở triển khai cũ không được làm sập trang giọng đọc."""
        async def boom(*_args, **_kwargs):
            raise RuntimeError("relation \"tts_providers\" does not exist")

        monkeypatch.setattr(tts_providers, "refresh_tts_providers", boom)
        res = await client.get("/api/v1/settings/tts", headers=SALE_HEADERS)
        assert res.status_code == 200
        providers = {item["provider"] for item in res.json()["catalog"]}
        assert {"browser", "openai", "viettel"} <= providers

    @pytest.mark.asyncio
    async def test_de_khoa_va_sua_don_gia_cho_nha_cung_cap_dung_san(self, client: AsyncClient):
        """Bản ghi đè: giữ nguyên vị trí trong danh mục, đổi đơn giá + nhập khoá."""
        override = dict(CUSTOM_PAYLOAD)
        override.update(
            provider="viettel",
            label="Viettel AI TTS (đã đối chiếu giá 2026)",
            price_per_1m_chars=350_000,
            default_model="viettel-tts",
            env_key="VIETTEL_TTS_TOKEN",
            api_key="viettel-token-abc",
        )
        created = await _create(client, override)
        assert created["custom"] is False and created["has_db_row"] is True
        assert created["price_per_1m_chars"] == 350_000
        assert created["key_source"] == "db"

        catalog = (await client.get("/api/v1/admin/tts/providers", headers=ADMIN_HEADERS)).json()["items"]
        codes = [item["provider"] for item in catalog]
        # Nhà cung cấp dựng sẵn giữ nguyên thứ tự (không bị đẩy xuống cuối như nhà cung cấp mới).
        assert codes.index("viettel") < codes.index("vbee")

    @pytest.mark.asyncio
    async def test_trung_ma_thi_bao_dung_la_dung_nut_sua(self, client: AsyncClient):
        await _create(client, CUSTOM_PAYLOAD)
        res = await client.post("/api/v1/admin/tts/providers", json=CUSTOM_PAYLOAD, headers=ADMIN_HEADERS)
        assert res.status_code == 409
        assert "Sửa" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_thieu_khoa_thi_tu_choi(self, client: AsyncClient):
        payload = dict(CUSTOM_PAYLOAD, provider="no-key-vendor", api_key="")
        res = await client.post("/api/v1/admin/tts/providers", json=payload, headers=ADMIN_HEADERS)
        assert res.status_code == 422


class TestSuaVaXoa:
    @pytest.mark.asyncio
    async def test_sua_giu_khoa_cu_khi_de_trong(self, client: AsyncClient):
        created = await _create(client, CUSTOM_PAYLOAD)
        payload = dict(CUSTOM_PAYLOAD, label="VieNeu (đổi tên)", api_key="")
        res = await client.put(
            f"/api/v1/admin/tts/providers/{created['provider_id']}", json=payload, headers=ADMIN_HEADERS
        )
        assert res.status_code == 200
        body = res.json()
        assert body["label"] == "VieNeu (đổi tên)"
        assert body["api_key_configured"] is True, "để trống khoá khi sửa = giữ khoá cũ"
        assert body["api_key_masked"] == created["api_key_masked"]

    @pytest.mark.asyncio
    async def test_doi_khoa_thi_dung_khoa_moi(self, client: AsyncClient):
        created = await _create(client, CUSTOM_PAYLOAD)
        payload = dict(CUSTOM_PAYLOAD, api_key="tok-vieneu-9999")
        res = await client.put(
            f"/api/v1/admin/tts/providers/{created['provider_id']}", json=payload, headers=ADMIN_HEADERS
        )
        assert res.status_code == 200
        assert res.json()["api_key_masked"].endswith("9999")

    @pytest.mark.asyncio
    async def test_xoa_ban_ghi_de_nha_cung_cap_dung_san_van_con(self, client: AsyncClient):
        override = dict(CUSTOM_PAYLOAD, provider="vbee", price_per_1m_chars=700_000)
        created = await _create(client, override)
        res = await client.delete(
            f"/api/v1/admin/tts/providers/{created['provider_id']}", headers=ADMIN_HEADERS
        )
        assert res.status_code == 200
        assert res.json() == {
            "ok": True,
            "provider_id": created["provider_id"],
            "provider": "vbee",
            "still_available": True,
            "used_by_scopes": 0,
        }
        items = {i["provider"]: i for i in (await client.get("/api/v1/admin/tts/providers", headers=ADMIN_HEADERS)).json()["items"]}
        assert "vbee" in items, "xoá bản ghi đè không được làm mất nhà cung cấp dựng sẵn"
        assert items["vbee"]["price_per_1m_chars"] == 598_000, "quay về đơn giá dựng sẵn"
        assert items["vbee"]["has_db_row"] is False

    @pytest.mark.asyncio
    async def test_xoa_nha_cung_cap_tu_them_thi_bien_mat(self, client: AsyncClient):
        created = await _create(client, CUSTOM_PAYLOAD)
        res = await client.delete(
            f"/api/v1/admin/tts/providers/{created['provider_id']}", headers=ADMIN_HEADERS
        )
        assert res.json()["still_available"] is False
        codes = [i["provider"] for i in (await client.get("/api/v1/admin/tts/providers", headers=ADMIN_HEADERS)).json()["items"]]
        assert "vieneu" not in codes

    @pytest.mark.asyncio
    async def test_xoa_nha_cung_cap_dang_duoc_dung_thi_canh_bao_va_tu_roi_ve_mac_dinh(self, client: AsyncClient):
        """Quản trị viên xoá nhà cung cấp trong khi vẫn có người chọn nó ⇒ không được để trang lỗi 500."""
        created = await _create(client, CUSTOM_PAYLOAD)
        saved = await client.put(
            "/api/v1/settings/tts",
            json={"scope": "default", "provider": "vieneu", "voice": "vi-female-01"},
            headers=ADMIN_HEADERS,
        )
        assert saved.status_code == 200 and saved.json()["effective"]["provider"] == "vieneu"

        res = await client.delete(f"/api/v1/admin/tts/providers/{created['provider_id']}", headers=ADMIN_HEADERS)
        assert res.json()["used_by_scopes"] == 1, "phải nói ra là đang có thiết lập dùng nhà cung cấp này"

        after = await client.get("/api/v1/settings/tts", headers=ADMIN_HEADERS)
        assert after.status_code == 200, "xoá nhà cung cấp không được làm sập trang giọng đọc"
        assert after.json()["effective"]["provider"] == "browser"

    @pytest.mark.asyncio
    async def test_khong_lo_khoa_ra_bat_ky_phan_hoi_nao(self, client: AsyncClient):
        created = await _create(client, CUSTOM_PAYLOAD)
        for method, url in (
            ("get", "/api/v1/admin/tts/providers"),
            ("get", "/api/v1/settings/tts"),
        ):
            res = await getattr(client, method)(url, headers=ADMIN_HEADERS)
            assert "tok-vieneu-1234" not in res.text
            assert '"api_key"' not in res.text
        assert created["api_key_masked"] != "tok-vieneu-1234"


class TestKhoaDbThangEnv:
    @pytest.mark.asyncio
    async def test_db_thang_env_va_xoa_thi_quay_lai_env(self, client: AsyncClient, monkeypatch):
        monkeypatch.setenv("VIETTEL_TTS_TOKEN", "env-token-1111")
        items = {i["provider"]: i for i in (await client.get("/api/v1/admin/tts/providers", headers=ADMIN_HEADERS)).json()["items"]}
        assert items["viettel"]["key_source"] == "env"

        override = dict(CUSTOM_PAYLOAD, provider="viettel", api_key="db-token-2222", price_per_1m_chars=320_000)
        created = await _create(client, override)
        items = {i["provider"]: i for i in (await client.get("/api/v1/admin/tts/providers", headers=ADMIN_HEADERS)).json()["items"]}
        assert items["viettel"]["key_source"] == "db", "khoá trong DB phải thắng ENV"

        await client.delete(f"/api/v1/admin/tts/providers/{created['provider_id']}", headers=ADMIN_HEADERS)
        items = {i["provider"]: i for i in (await client.get("/api/v1/admin/tts/providers", headers=ADMIN_HEADERS)).json()["items"]}
        assert items["viettel"]["key_source"] == "env", "xoá bản ghi thì quay lại khoá ENV"

    @pytest.mark.asyncio
    async def test_khoa_mau_trong_env_khong_tinh_la_co_khoa(self, client: AsyncClient, monkeypatch):
        monkeypatch.setenv("AZURE_SPEECH_KEY", "your-azure-key-here")
        items = {i["provider"]: i for i in (await client.get("/api/v1/admin/tts/providers", headers=ADMIN_HEADERS)).json()["items"]}
        assert items["azure"]["api_key_configured"] is False
        assert items["azure"]["key_source"] == "none"


class TestTestKetNoi:
    @pytest.mark.asyncio
    async def test_browser_khong_can_khoa(self, client: AsyncClient):
        res = await client.post("/api/v1/admin/tts/providers/browser/test", headers=ADMIN_HEADERS)
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True and body["status"] == "NO_KEY_NEEDED"

    @pytest.mark.asyncio
    async def test_chua_co_khoa_thi_noi_that(self, client: AsyncClient, monkeypatch):
        monkeypatch.delenv("VIETTEL_TTS_TOKEN", raising=False)
        res = await client.post("/api/v1/admin/tts/providers/viettel/test", headers=ADMIN_HEADERS)
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is False and body["status"] == "NOT_CONFIGURED"
        assert "VIETTEL_TTS_TOKEN" in body["detail"]

    @pytest.mark.asyncio
    async def test_server_gia_openai_compatible_thi_bao_ok(self, client: AsyncClient, provider_server):
        base_url, _seen = provider_server("ok")
        override = dict(
            CUSTOM_PAYLOAD,
            provider="openai",
            label="OpenAI TTS (qua gateway nội bộ)",
            base_url=base_url,
            api_key="sk-gateway-1234",
            price_per_1m_chars=15,
            currency="USD",
        )
        created = await _create(client, override)
        res = await client.post(
            f"/api/v1/admin/tts/providers/{created['provider_id']}/test", headers=ADMIN_HEADERS
        )
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True and body["status"] == "OK"
        assert body["method"] == "GET /models" and body["latency_ms"] >= 0

        # Lịch sử kiểm tra được lưu vào bản ghi để UI hiện lại.
        listing = {i["provider"]: i for i in (await client.get("/api/v1/admin/tts/providers", headers=ADMIN_HEADERS)).json()["items"]}
        assert listing["openai"]["last_test_status"] == "OK"

    @pytest.mark.asyncio
    async def test_server_gia_tu_choi_khoa(self, client: AsyncClient, provider_server):
        base_url, _seen = provider_server("bad-key")
        override = dict(CUSTOM_PAYLOAD, provider="openai", base_url=base_url, api_key="sk-sai-9999")
        created = await _create(client, override)
        body = (
            await client.post(f"/api/v1/admin/tts/providers/{created['provider_id']}/test", headers=ADMIN_HEADERS)
        ).json()
        assert body["ok"] is False and body["status"] == "ERROR"
        assert "401" in body["detail"]

    @pytest.mark.asyncio
    async def test_nha_cung_cap_khong_mo_endpoint_kiem_tra_thi_noi_that(self, client: AsyncClient, provider_server):
        """Không được báo xanh giả: phải nói rõ là không kiểm tra tự động được + cách kiểm bằng tay."""
        base_url, _seen = provider_server("ok")
        custom = dict(CUSTOM_PAYLOAD, provider="vieneu", base_url=base_url, api_key="tok-vieneu-1234")
        created = await _create(client, custom)
        body = (
            await client.post(f"/api/v1/admin/tts/providers/{created['provider_id']}/test", headers=ADMIN_HEADERS)
        ).json()
        assert body["ok"] is False and body["status"] == "UNSUPPORTED"
        assert "Đọc" in body["detail"], "phải chỉ cách kiểm bằng tay"

    @pytest.mark.asyncio
    async def test_test_nha_cung_cap_dung_san_chua_co_ban_ghi(self, client: AsyncClient, provider_server):
        """Bấm Test cho nhà cung cấp dựng sẵn (chưa có bản ghi DB) vẫn phải chạy được."""
        monkeypatch_url, _seen = provider_server("bad-key")
        res = await client.post("/api/v1/admin/tts/providers/openai/test", headers=ADMIN_HEADERS)
        assert res.status_code == 200
        assert res.json()["status"] in {"NOT_CONFIGURED", "ERROR", "OK"}
        assert monkeypatch_url  # giữ server sống trong suốt test
