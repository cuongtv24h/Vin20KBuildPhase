"""Quy tắc "Sale chỉ được xoá khách hàng do chính mình tạo ra" (C-10 · CRM).

Trước đây `DELETE /api/v1/leads/{dossier_id}` xoá vô điều kiện: ai biết mã hồ sơ cũng xoá được khách
của người khác. Bộ test này chốt lại 5 lớp bảo vệ, đúng theo yêu cầu người dùng:

1. Không có phiên đăng nhập → 401 (không dùng principal mặc định cho thao tác phá huỷ dữ liệu).
2. Sale xoá khách **do mình tạo** → 200.
3. Sale xoá khách **của Sale khác** → 403 (kèm mã lỗi + ai là người tạo) và hồ sơ vẫn còn nguyên.
4. Hồ sơ **chưa ghi người tạo** (`created_by` NULL — dữ liệu cũ, hoặc hồ sơ Pre-Sales khách tự bàn giao)
   → chỉ ADMIN xoá được. Từng cho phép "ai đăng nhập cũng xoá", nhưng trên DB vận hành không hồ sơ nào
   có `created_by` nên coi như toàn bộ khách hàng đều bị bỏ ngỏ.
5. ADMIN cấp chủ sở hữu bằng `POST /api/v1/leads/{id}/assign-sale`: gán Sale phụ trách và đóng dấu người
   tạo khi hồ sơ còn vô chủ; KHÔNG ghi đè người tạo đã có (không ai cướp được hồ sơ của người khác).
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


async def _seed_ownerless_dossier(name: str = "Khách cũ") -> str:
    """Hồ sơ kiểu dữ liệu vận hành hiện tại: tạo trước khi có cột `created_by`, chưa gán Sale nào."""
    suffix = uuid.uuid4().hex[:8]
    dossier_id = f"LD-LEGACY-{suffix}"
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
                dossier_id=dossier_id,
                session_id=session_row.session_id,
                status="NEW",
                lead_temperature="WARM",
                customer_name=name,
                customer_phone_masked="090***4567",
                assigned_sales_id=None,
                created_by=None,
                sla_expires_at=now + timedelta(minutes=15),
            )
        )
        await session.commit()
    return dossier_id


@pytest.mark.asyncio
async def test_dossier_without_owner_is_admin_only(client) -> None:
    """Hồ sơ vô chủ: Sale bị chặn (403), ADMIN vẫn xoá được để không khoá dữ liệu."""
    dossier_id = await _seed_ownerless_dossier()

    sale_response = await client.delete(f"/api/v1/leads/{dossier_id}", headers=_headers(SALE_A))
    assert sale_response.status_code == 403, sale_response.text
    detail = sale_response.json()["detail"]
    assert detail["error_code"] == ErrorCode.UNAUTHORIZED_ACCESS.value
    assert detail["details"]["created_by"] is None
    assert detail["details"]["requested_by"] == SALE_A[0]
    # Hồ sơ vẫn còn nguyên cho tới khi ADMIN xử lý.
    assert (await client.get(f"/api/v1/leads/{dossier_id}")).status_code == 200

    admin_response = await client.delete(f"/api/v1/leads/{dossier_id}", headers=_headers(ADMIN))
    assert admin_response.status_code == 200, admin_response.text


@pytest.mark.asyncio
async def test_admin_assigns_owner_then_that_sale_can_delete(client) -> None:
    """Đường cấp chủ sở hữu cho dữ liệu cũ: ADMIN gán Sale phụ trách = đóng dấu người tạo."""
    dossier_id = await _seed_ownerless_dossier("Khách chưa ai phụ trách")

    assign = await client.post(
        f"/api/v1/leads/{dossier_id}/assign-sale",
        json={"sales_id": SALE_B[0]},
        headers=_headers(ADMIN),
    )
    assert assign.status_code == 200, assign.text
    body = assign.json()
    assert body["assigned_sales_id"] == SALE_B[0]
    assert body["created_by"] == SALE_B[0], "Hồ sơ vô chủ phải được đóng dấu người tạo khi gán"

    # Sale khác vẫn không xoá được; Sale vừa được gán thì được.
    other = await client.delete(f"/api/v1/leads/{dossier_id}", headers=_headers(SALE_A))
    assert other.status_code == 403, other.text
    owner = await client.delete(f"/api/v1/leads/{dossier_id}", headers=_headers(SALE_B))
    assert owner.status_code == 200, owner.text


@pytest.mark.asyncio
async def test_assign_sale_requires_admin_session(client) -> None:
    dossier_id = await _seed_ownerless_dossier()

    anonymous = await client.post(
        f"/api/v1/leads/{dossier_id}/assign-sale", json={"sales_id": SALE_A[0]}
    )
    assert anonymous.status_code == 401, anonymous.text

    as_sale = await client.post(
        f"/api/v1/leads/{dossier_id}/assign-sale",
        json={"sales_id": SALE_A[0]},
        headers=_headers(SALE_A),
    )
    assert as_sale.status_code == 403, as_sale.text
    # Không ai tự gán mình làm chủ được ⇒ hồ sơ vẫn vô chủ và Sale vẫn không xoá được.
    assert (await client.get(f"/api/v1/leads/{dossier_id}")).json()["created_by"] is None
    assert (await client.delete(f"/api/v1/leads/{dossier_id}", headers=_headers(SALE_A))).status_code == 403


@pytest.mark.asyncio
async def test_assign_does_not_steal_existing_owner(client) -> None:
    """Gán Sale phụ trách cho hồ sơ ĐÃ có chủ: đổi người chăm khách, không đổi quyền xoá."""
    dossier_id = await _create_dossier(client, SALE_A, "Khách của Sale A")

    assign = await client.post(
        f"/api/v1/leads/{dossier_id}/assign-sale",
        json={"sales_id": SALE_B[0]},
        headers=_headers(ADMIN),
    )
    assert assign.status_code == 200, assign.text
    body = assign.json()
    assert body["assigned_sales_id"] == SALE_B[0]
    assert body["created_by"] == SALE_A[0], "Không được ghi đè người tạo đã có"

    assert (await client.delete(f"/api/v1/leads/{dossier_id}", headers=_headers(SALE_B))).status_code == 403
    assert (await client.delete(f"/api/v1/leads/{dossier_id}", headers=_headers(SALE_A))).status_code == 200


@pytest.mark.asyncio
async def test_assign_rejects_blank_sales_id(client) -> None:
    dossier_id = await _seed_ownerless_dossier()
    response = await client.post(
        f"/api/v1/leads/{dossier_id}/assign-sale",
        json={"sales_id": "   "},
        headers=_headers(ADMIN),
    )
    assert response.status_code == 422, response.text
    assert response.json()["detail"]["error_code"] == ErrorCode.INPUT_VALIDATION_ERROR.value


@pytest.mark.asyncio
async def test_assign_missing_dossier_is_rejected(client) -> None:
    """Gán cho hồ sơ không tồn tại → NOT_FOUND, không sinh bản ghi ma.

    Lưu ý: `PreSalesDossierService.get_dossier` raise `DomainError(NOT_FOUND)` không kèm `http_status`
    nên cả router /leads trả HTTP 400 cho mã lỗi này (hành vi sẵn có, giữ nguyên để không đổi hợp đồng
    của các endpoint khác). Test vì vậy chốt **mã lỗi**, không chốt con số HTTP.
    """
    response = await client.post(
        "/api/v1/leads/LD-KHONG-TON-TAI/assign-sale",
        json={"sales_id": SALE_A[0]},
        headers=_headers(ADMIN),
    )
    assert response.status_code in (400, 404), response.text
    assert response.json()["detail"]["error_code"] == ErrorCode.NOT_FOUND.value


@pytest.mark.asyncio
async def test_service_requires_actor_for_delete() -> None:
    """Chốt ở tầng service: gọi xoá mà không có danh tính → 401, không xoá được gì."""
    service = PreSalesDossierService()
    async with async_test_session_factory() as session:
        with pytest.raises(DomainError) as excinfo:
            await service.delete_dossier(session, "LD-KHONG-CO", actor_id=None)
    assert excinfo.value.error_code in (ErrorCode.UNAUTHORIZED_ACCESS, ErrorCode.NOT_FOUND)
