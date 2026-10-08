"""Phân công Sale phụ trách khi khách TỰ bàn giao (Pre-Sales) — `PreSalesDossierService`.

Vì sao có: hồ sơ sinh từ luồng khách đồng ý bàn giao trước đây không ghi `assigned_sales_id` lẫn
`created_by` ⇒ vô chủ. Theo luật xoá mới thì chỉ ADMIN xử lý được, và không Sale nào thấy "khách của
mình" trong CRM — trong khi bản mock đã chia hồ sơ theo tải từ lâu (`pickSale`). Bộ test này chốt:

1. Chọn Sale ÍT hồ sơ chờ nhất (không tính hồ sơ đã chuyển báo giá), không chọn ADMIN/MANAGER.
2. Hoà tải thì chọn theo mã nhân viên — kết quả ổn định, không phụ thuộc thứ tự DB trả về.
3. Không có tài khoản SALE nào ⇒ trả `None`, hồ sơ vô chủ để ADMIN gán (không đoán bừa).
4. Hồ sơ bàn giao có chủ sở hữu ngay, status vẫn `NEW` để SLA 15 phút tiếp tục chạy.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete

from src.contracts.errors import DomainError
from src.db.models import (
    CustomerConsentModel,
    LeadDossierModel,
    PreSalesPlanModel,
    PreSalesSessionModel,
    UserModel,
)
from src.services.dossier.service import PreSalesDossierService
from tests.conftest import async_test_session_factory


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    """DB in-memory dùng chung cả phiên test (StaticPool) nên phải dọn trước mỗi ca.

    Không dọn thì (a) `users.email` UNIQUE nổ khi ca sau seed lại cùng nhân viên, và (b) hồ sơ của ca
    trước còn nằm trong bảng sẽ bị đếm vào "tải" ⇒ `pick_least_loaded_sale` chọn sai người.
    """
    async with async_test_session_factory() as session:
        for model in (
            LeadDossierModel,
            CustomerConsentModel,
            PreSalesPlanModel,
            PreSalesSessionModel,
            UserModel,
        ):
            await session.execute(delete(model))
        await session.commit()


async def _seed_users(*accounts: tuple[str, str]) -> None:
    """Ghi danh sách nhân viên vào bảng `users` (user_id, role)."""
    async with async_test_session_factory() as session:
        for user_id, role in accounts:
            session.add(
                UserModel(
                    user=user_id,
                    password="khong-dung-trong-test",
                    email=f"{user_id.lower()}@vlandfuture.vn",
                    role=role,
                )
            )
        await session.commit()


async def _seed_dossier(sales_id: str | None, *, converted: bool = False) -> str:
    """Tạo một hồ sơ (tuỳ chọn đã chuyển báo giá) để tạo "tải" cho một Sale."""
    service = PreSalesDossierService()
    async with async_test_session_factory() as session:
        pre_sales_session = await service.create_session(db=session, tenant_id="DEFAULT")
        dossier = await service.create_dossier(
            session,
            session_id=pre_sales_session.session_id,
            customer_name=f"Khách của {sales_id or 'pool'} {uuid.uuid4().hex[:6]}",
            customer_phone="0901234567",
            assigned_sales_id=sales_id,
            created_by=sales_id,
        )
        if converted:
            dossier = await service.mark_converted(session, dossier.dossier_id, f"Q-{uuid.uuid4().hex[:6]}")
        await session.commit()
        return dossier.dossier_id


@pytest.mark.asyncio
async def test_chon_sale_it_ho_so_nhat_va_bo_qua_vai_tro_khac() -> None:
    await _seed_users(("SALES-001", "SALE"), ("SALES-002", "SALES"), ("ADMIN-001", "ADMIN"), ("MGR-001", "MANAGER"))
    await _seed_dossier("SALES-001")
    await _seed_dossier("SALES-001")

    service = PreSalesDossierService()
    async with async_test_session_factory() as session:
        assert await service.pick_least_loaded_sale(session) == "SALES-002"


@pytest.mark.asyncio
async def test_ho_so_da_chuyen_bao_gia_khong_tinh_vao_tai() -> None:
    """Khách đã chốt (ra báo giá) không còn là việc đang chờ ⇒ không đè lên Sale đó."""
    await _seed_users(("SALES-001", "SALE"), ("SALES-002", "SALE"))
    for _ in range(3):
        await _seed_dossier("SALES-001", converted=True)
    await _seed_dossier("SALES-002")

    service = PreSalesDossierService()
    async with async_test_session_factory() as session:
        assert await service.pick_least_loaded_sale(session) == "SALES-001"


@pytest.mark.asyncio
async def test_hoa_tai_thi_chon_theo_ma_nhan_vien() -> None:
    await _seed_users(("SALES-002", "SALE"), ("SALES-001", "SALE"), ("SALES-003", "SALES"))

    service = PreSalesDossierService()
    async with async_test_session_factory() as session:
        assert await service.pick_least_loaded_sale(session) == "SALES-001"


@pytest.mark.asyncio
async def test_khong_co_sale_thi_khong_doan_bua() -> None:
    """DB chỉ có ADMIN/MANAGER: trả None để hồ sơ vô chủ, ADMIN gán sau — không gán cho quản lý."""
    await _seed_users(("ADMIN-001", "ADMIN"), ("MGR-001", "MANAGER"))

    service = PreSalesDossierService()
    async with async_test_session_factory() as session:
        assert await service.pick_least_loaded_sale(session) is None

        pre_sales_session = await service.create_session(db=session, tenant_id="DEFAULT")
        dossier = await service.create_handoff_dossier(
            session,
            session_id=pre_sales_session.session_id,
            customer_name="Khách tự bàn giao",
            customer_phone="0901234567",
        )
        await session.commit()
        assert dossier.assigned_sales_id is None
        assert dossier.created_by is None


@pytest.mark.asyncio
async def test_ho_so_ban_giao_co_chu_so_huu_va_sale_do_xoa_duoc() -> None:
    await _seed_users(("SALES-001", "SALE"), ("SALES-002", "SALE"))
    await _seed_dossier("SALES-001")  # SALES-001 đang bận hơn

    service = PreSalesDossierService()
    async with async_test_session_factory() as session:
        pre_sales_session = await service.create_session(db=session, tenant_id="DEFAULT")
        dossier = await service.create_handoff_dossier(
            session,
            session_id=pre_sales_session.session_id,
            customer_name="Khách tự bàn giao",
            customer_phone="0901234567",
        )
        await session.commit()

        assert dossier.assigned_sales_id == "SALES-002"
        assert dossier.created_by == "SALES-002", "Chủ sở hữu phải là Sale được giao"
        assert dossier.status == "NEW", "SLA 15 phút phải tiếp tục chạy tới khi Sale bấm nhận lead"

        # Sale được giao xoá được; Sale khác thì không.
        with pytest.raises(DomainError):
            await service.delete_dossier(session, dossier.dossier_id, actor_id="SALES-001")
        assert await service.delete_dossier(session, dossier.dossier_id, actor_id="SALES-002") is True
        await session.commit()
