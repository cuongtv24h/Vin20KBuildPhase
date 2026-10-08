"""Quy tắc "Sale chỉ được xoá khách hàng do chính mình tạo ra" (C-10 · CRM).

Trước đây `DELETE /api/v1/leads/{dossier_id}` xoá vô điều kiện: ai biết mã hồ sơ cũng xoá được khách
của người khác. Bộ test này chốt lại 4 lớp bảo vệ, đúng theo yêu cầu người dùng:

1. Không có phiên đăng nhập → 401 (không dùng principal mặc định cho thao tác phá huỷ dữ liệu).
2. Sale xoá khách **do mình tạo** → 200.
3. Sale xoá khách **của Sale khác** → 403 (kèm mã lỗi + ai là người tạo) và hồ sơ vẫn còn nguyên.
4. ADMIN được xoá hộ; hồ sơ di sản (`created_by` NULL) vẫn xoá được để không khoá dữ liệu cũ.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from src.api.endpoints import leads as leads_endpoints
from src.contracts.errors import DomainError, ErrorCode
from src.db.models import LeadDossierModel, PreSalesSessionModel
from src.services.dossier.service import PreSalesDossierService
from tests.conftest import async_test_session_factory

SALE_A = ("SALES-001", "SALE")
SALE_B = ("SALES-002", "SALE")
ADMIN = ("ADMIN-001", "ADMIN")


@pytest.fixture(autouse=True)
def _leads_endpoints_use_test_db(monkeypatch):
    """Ép các endpoint /leads dùng DB trong bộ nhớ của test.

    Nhóm endpoint này gọi `async for db in get_db_session()` trực tiếp (không qua `Depends`) nên
    `app.dependency_overrides` của conftest không chạm tới — chúng sẽ nói chuyện với DB vận hành.
    Test phải chỉ đúng vào DB in-memory, nếu không sẽ ghi vào DB thật của máy chạy test.
    """

    async def _session_gen():
        async with async_test_session_factory() as session:
            yield session

    monkeypatch.setattr(leads_endpoints, "get_db_session", _session_gen)


def _headers(actor: tuple[str, str] | None) -> dict[str, str]:
    if actor is None:
        return {}
    user_id, role = actor
    return {
        "Authorization": f"Bearer {user_id}",
        "X-User-Id": user_id,
        "X-User-Role": role,
    }


async def _create_dossier(client, actor: tuple[str, str], name: str) -> str:
    """Tạo hồ sơ qua đúng đường HTTP mà Sales dùng (CRM → Thêm khách hàng)."""
    response = await client.post(
        "/api/v1/leads",
        json={"customer_name": name, "customer_phone": "0901234567"},
        headers=_headers(actor),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["created_by"] == actor[0], "Hồ sơ phải ghi nhận người tạo theo phiên đăng nhập"
    return body["dossier_id"]


@pytest.mark.asyncio
async def test_delete_without_login_is_rejected(client) -> None:
    """Không có Authorization → 401, dù hồ sơ có chủ hay không."""
    dossier_id = await _create_dossier(client, SALE_A, "Khách có chủ")
    response = await client.delete(f"/api/v1/leads/{dossier_id}")
    assert response.status_code == 401
    # Hồ sơ vẫn còn.
    assert (await client.get(f"/api/v1/leads/{dossier_id}")).status_code == 200


@pytest.mark.asyncio
async def test_sale_deletes_own_dossier(client) -> None:
    dossier_id = await _create_dossier(client, SALE_A, "Khách của chính mình")
    response = await client.delete(f"/api/v1/leads/{dossier_id}", headers=_headers(SALE_A))
    assert response.status_code == 200, response.text
    assert response.json() == {"deleted": True, "dossier_id": dossier_id}


@pytest.mark.asyncio
async def test_sale_cannot_delete_other_sales_dossier(client) -> None:
    """Điểm chốt của yêu cầu: khách của Sale khác thì KHÔNG xoá được."""
    dossier_id = await _create_dossier(client, SALE_B, "Khách của đồng nghiệp")

    response = await client.delete(f"/api/v1/leads/{dossier_id}", headers=_headers(SALE_A))

    assert response.status_code == 403, response.text
    detail = response.json()["detail"]
    assert detail["error_code"] == ErrorCode.UNAUTHORIZED_ACCESS.value
    assert detail["details"]["created_by"] == SALE_B[0]
    assert detail["details"]["requested_by"] == SALE_A[0]
    # Và hồ sơ của đồng nghiệp vẫn nguyên vẹn cho chủ sở hữu dùng.
    assert (await client.get(f"/api/v1/leads/{dossier_id}")).status_code == 200
    owner_delete = await client.delete(f"/api/v1/leads/{dossier_id}", headers=_headers(SALE_B))
    assert owner_delete.status_code == 200


@pytest.mark.asyncio
async def test_admin_can_delete_any_dossier(client) -> None:
    dossier_id = await _create_dossier(client, SALE_B, "Khách cần quản trị xoá hộ")
    response = await client.delete(f"/api/v1/leads/{dossier_id}", headers=_headers(ADMIN))
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_legacy_dossier_without_owner_is_still_deletable(client) -> None:
    """Hồ sơ tạo trước khi có cột `created_by` (NULL) không bị khoá cứng."""
    suffix = uuid.uuid4().hex[:8]
    legacy_id = f"LD-LEGACY-{suffix}"
    async with async_test_session_factory() as session:
        now = datetime.now(UTC)
        session_row = PreSalesSessionModel(
            session_id=f"SES-LEGACY-{suffix}",
            status="ACTIVE",
            constraints_json={"needs_summary": "hồ sơ cũ chưa có cột created_by"},
            expires_at=now + timedelta(minutes=30),
        )
        session.add(session_row)
        session.add(
            LeadDossierModel(
                dossier_id=legacy_id,
                session_id=session_row.session_id,
                status="NEW",
                lead_temperature="WARM",
                customer_name="Khách cũ",
                customer_phone_masked="090***4567",
                assigned_sales_id=None,
                created_by=None,
                sla_expires_at=now + timedelta(minutes=15),
            )
        )
        await session.commit()

    response = await client.delete(f"/api/v1/leads/{legacy_id}", headers=_headers(SALE_A))
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_service_requires_actor_for_delete() -> None:
    """Chốt ở tầng service: gọi xoá mà không có danh tính → 401, không xoá được gì."""
    service = PreSalesDossierService()
    async with async_test_session_factory() as session:
        with pytest.raises(DomainError) as excinfo:
            await service.delete_dossier(session, "LD-KHONG-CO", actor_id=None)
    assert excinfo.value.error_code in (ErrorCode.UNAUTHORIZED_ACCESS, ErrorCode.NOT_FOUND)
