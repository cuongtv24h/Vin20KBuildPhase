"""
Unit test cho Module Quản trị Admin (admin_cp) & Xác thực DB với mã hóa MD5.
Cấu trúc: user | password | email | phone (role phân quyền).
"""

from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import delete

from src.db.models import UserModel
from src.db.session import async_session_factory


@pytest.mark.asyncio
async def test_admin_cp_lifecycle_and_md5_auth(client):
    # Dọn dẹp trước khi chạy test
    async with async_session_factory() as session:
        await session.execute(delete(UserModel).where(UserModel.email.like("%@test-vland.vn")))
        await session.commit()

    # 1. Kiểm tra setup-status ban đầu
    res = await client.get("/api/v1/admin/setup-status")
    assert res.status_code == 200
    data = res.json()
    assert data["initialized"] is False
    assert data["total_users"] == 0

    # 2. Khởi tạo tài khoản Quản trị viên đầu tiên (user, password, email, phone)
    admin_user = "admin_root"
    admin_email = "root.admin@test-vland.vn"
    admin_pass = "Admin@12345"
    admin_phone = "0912 345 678"
    admin_setup_payload = {
        "user": admin_user,
        "password": admin_pass,
        "email": admin_email,
        "phone": admin_phone,
    }

    # Gọi setup lần 1 -> THÀNH CÔNG
    res = await client.post("/api/v1/admin/setup", json=admin_setup_payload)
    assert res.status_code == 201
    setup_data = res.json()
    assert setup_data["status"] == "success"
    assert setup_data["user"]["user"] == admin_user
    assert setup_data["user"]["email"] == admin_email
    assert setup_data["user"]["role"] == "ADMIN"

    # Kiểm tra mật khẩu trong DB được mã hóa MD5
    expected_md5 = hashlib.md5(admin_pass.encode("utf-8")).hexdigest()
    from tests.conftest import async_test_session_factory
    async with async_test_session_factory() as session:
        from sqlalchemy import select
        user_in_db = await session.scalar(select(UserModel).where(UserModel.user == admin_user))
        assert user_in_db is not None
        assert user_in_db.password == expected_md5
        assert user_in_db.email == admin_email
        assert user_in_db.phone == admin_phone

    # 3. Gọi setup lần 2 -> PHẢI BỊ CHẶN (HTTP 400)
    res_blocked = await client.post("/api/v1/admin/setup", json=admin_setup_payload)
    assert res_blocked.status_code == 400
    assert "Không thể thực hiện khởi tạo lại" in res_blocked.json()["detail"]

    # 4. Đăng nhập qua POST /api/v1/auth/login (hỗ trợ cả username và email)
    login_by_user_res = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user, "password": admin_pass},
    )
    assert login_by_user_res.status_code == 200
    assert login_by_user_res.json()["user"]["role"] == "ADMIN"

    login_by_email_res = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_email, "password": admin_pass},
    )
    assert login_by_email_res.status_code == 200
    login_data = login_by_email_res.json()
    assert login_data["user"]["email"] == admin_email
    assert login_data["user"]["role"] == "ADMIN"

    # Đăng nhập sai mật khẩu -> 401
    wrong_pass_res = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_email, "password": "wrong_password"},
    )
    assert wrong_pass_res.status_code == 401

    # 5. Admin tạo user mới (Role SALE) sử dụng Authorization Bearer token
    admin_token = login_data["access_token"]
    admin_headers = {
        "Authorization": f"Bearer {admin_token}",
    }
    sale_payload = {
        "user": "sale_nam",
        "password": "Sale@123",
        "email": "sale.nam@test-vland.vn",
        "phone": "0987 654 321",
        "role": "SALE",
    }
    create_user_res = await client.post(
        "/api/v1/admin/users",
        json=sale_payload,
        headers=admin_headers,
    )
    assert create_user_res.status_code == 201
    sale_data = create_user_res.json()
    assert sale_data["user"] == "sale_nam"
    assert sale_data["role"] == "SALE"

    # 6. Lấy danh sách users
    list_res = await client.get("/api/v1/admin/users", headers=admin_headers)
    assert list_res.status_code == 200
    users_list = list_res.json()
    users_names = [u["user"] for u in users_list]
    assert admin_user in users_names
    assert "sale_nam" in users_names

    # 7. Cập nhật phân quyền / đổi thông tin user
    update_res = await client.put(
        "/api/v1/admin/users/sale_nam",
        json={"role": "MANAGER", "phone": "0900 111 222"},
        headers=admin_headers,
    )
    assert update_res.status_code == 200
    updated_user = update_res.json()
    assert updated_user["role"] == "MANAGER"
    assert updated_user["phone"] == "0900 111 222"

    # 8. Xóa user
    del_res = await client.delete("/api/v1/admin/users/sale_nam", headers=admin_headers)
    assert del_res.status_code == 200

    # Dọn dẹp dữ liệu test
    async with async_session_factory() as session:
        await session.execute(delete(UserModel).where(UserModel.email.like("%@test-vland.vn")))
        await session.commit()
