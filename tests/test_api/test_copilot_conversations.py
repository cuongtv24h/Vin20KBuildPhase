"""Lịch sử hội thoại Copilot: giữ được qua các lượt và tra cứu lại được.

Trước đây hội thoại chỉ nằm trong state React nên đổi trang là mất. Test này khoá hợp đồng API:
tạo cuộc → ghi lượt → liệt kê → đọc lại → đổi tên → xoá, kèm ranh giới **chỉ thấy hội thoại của mình**
và yêu cầu đăng nhập.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.api.deps import create_access_token

SALE_TOKEN = create_access_token("nam.hoang@vlandfuture.vn", "SALE")
OTHER_SALE_TOKEN = create_access_token("trang.le@vlandfuture.vn", "SALE")
SALE_HEADERS = {"Authorization": f"Bearer {SALE_TOKEN}"}
OTHER_HEADERS = {"Authorization": f"Bearer {OTHER_SALE_TOKEN}"}


@pytest.fixture(autouse=True)
def isolate_history(tmp_path, monkeypatch):
    """Mỗi test dùng file lịch sử riêng — không đụng dữ liệu thật."""
    monkeypatch.setenv("COPILOT_HISTORY_PATH", str(tmp_path / "conversations.json"))
    yield


@pytest.mark.asyncio
async def test_can_dang_nhap_bat_buoc(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/copilot/conversations")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_tao_ghi_luot_roi_doc_lai(client: AsyncClient) -> None:
    # 1. Ghi một lượt (chưa có conversation_id → tự tạo cuộc mới)
    turn = await client.post(
        "/api/v1/copilot/conversations/turns",
        json={
            "user_message": "Chính sách thanh toán sớm là bao nhiêu?",
            "assistant_message": "Dạ 8.0% theo Điều 4 Khoản 2b.",
            "citations": [{"policy_id": "CSBH-ZEN-2026-V3.1", "section": "Điều 4, Khoản 2b"}],
        },
        headers=SALE_HEADERS,
    )
    assert turn.status_code == 201
    created = turn.json()
    conversation_id = created["conversation_id"]
    assert conversation_id.startswith("CNV-")
    assert created["message_count"] == 2
    assert created["title"].startswith("Chính sách thanh toán sớm")
    assert [m["role"] for m in created["messages"]] == ["user", "assistant"]
    assert created["messages"][1]["citations"][0]["policy_id"] == "CSBH-ZEN-2026-V3.1"

    # 2. Ghi tiếp lượt thứ hai vào cùng cuộc
    turn2 = await client.post(
        "/api/v1/copilot/conversations/turns",
        json={
            "conversation_id": conversation_id,
            "user_message": "Còn căn nào 2 phòng ngủ?",
            "assistant_message": "Dạ còn 3 căn R-02.",
        },
        headers=SALE_HEADERS,
    )
    assert turn2.status_code == 201
    assert turn2.json()["message_count"] == 4

    # 3. Đổi trang rồi quay lại: liệt kê thấy cuộc cũ
    listing = await client.get("/api/v1/copilot/conversations", headers=SALE_HEADERS)
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert [i["conversation_id"] for i in items] == [conversation_id]
    assert items[0]["message_count"] == 4
    assert items[0]["last_message"].startswith("Dạ còn 3 căn")

    # 4. Đọc lại toàn bộ nội dung
    detail = await client.get(f"/api/v1/copilot/conversations/{conversation_id}", headers=SALE_HEADERS)
    assert detail.status_code == 200
    contents = [m["content"] for m in detail.json()["messages"]]
    assert contents[0] == "Chính sách thanh toán sớm là bao nhiêu?"
    assert contents[-1] == "Dạ còn 3 căn R-02."


@pytest.mark.asyncio
async def test_chi_doc_duoc_hoi_thoai_cua_minh(client: AsyncClient) -> None:
    created = (
        await client.post(
            "/api/v1/copilot/conversations/turns",
            json={"user_message": "Câu hỏi riêng tư", "assistant_message": "Trả lời"},
            headers=SALE_HEADERS,
        )
    ).json()

    # Người khác không thấy trong danh sách…
    other_list = (await client.get("/api/v1/copilot/conversations", headers=OTHER_HEADERS)).json()
    assert other_list["items"] == []
    # …và mở trực tiếp bằng id cũng bị 404 (không phải 403 để không lộ sự tồn tại)
    assert (
        await client.get(f"/api/v1/copilot/conversations/{created['conversation_id']}", headers=OTHER_HEADERS)
    ).status_code == 404


@pytest.mark.asyncio
async def test_doi_ten_va_xoa(client: AsyncClient) -> None:
    created = (
        await client.post(
            "/api/v1/copilot/conversations/turns",
            json={"user_message": "Hỏi về giỏ hàng", "assistant_message": "Dạ"},
            headers=SALE_HEADERS,
        )
    ).json()
    cid = created["conversation_id"]

    renamed = await client.patch(
        f"/api/v1/copilot/conversations/{cid}", json={"title": "Khách Nguyễn Văn An"}, headers=SALE_HEADERS
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Khách Nguyễn Văn An"

    deleted = await client.delete(f"/api/v1/copilot/conversations/{cid}", headers=SALE_HEADERS)
    assert deleted.status_code == 200
    assert (await client.get(f"/api/v1/copilot/conversations/{cid}", headers=SALE_HEADERS)).status_code == 404
    # Xoá lần hai → 404
    assert (await client.delete(f"/api/v1/copilot/conversations/{cid}", headers=SALE_HEADERS)).status_code == 404


@pytest.mark.asyncio
async def test_tao_cuoc_trong_roi_dat_ten_sau(client: AsyncClient) -> None:
    created = await client.post("/api/v1/copilot/conversations", json={"title": "Tư vấn căn 2BR"}, headers=SALE_HEADERS)
    assert created.status_code == 201
    body = created.json()
    assert body["title"] == "Tư vấn căn 2BR"
    assert body["messages"] == []
    assert body["message_count"] == 0
