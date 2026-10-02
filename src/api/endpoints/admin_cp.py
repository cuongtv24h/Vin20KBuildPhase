"""
Module Quản trị Admin (Admin Control Panel - admin_cp).
Quản lý người dùng, phân quyền RBAC và khởi tạo Quản trị viên ban đầu.
Cấu trúc người dùng: user | password | email | phone (kèm role phân quyền).
Mã hóa mật khẩu bằng MD5.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import Principal, create_access_token, get_current_principal
from src.db.models import UserModel
from src.db.session import get_db_session

router = APIRouter(prefix="/api/v1/admin", tags=["admin_cp"])


def hash_md5(password: str) -> str:
    """Mã hóa mật khẩu bằng thuật toán MD5."""
    return hashlib.md5(password.strip().encode("utf-8")).hexdigest()


def verify_md5(plain_password: str, hashed_password: str) -> bool:
    """Kiểm tra mật khẩu khớp với mã băm MD5."""
    return hash_md5(plain_password) == hashed_password


# -----------------------------------------------------------------------------
# Pydantic Schemas
# -----------------------------------------------------------------------------
class SetupStatusResponse(BaseModel):
    initialized: bool
    total_users: int
    has_admin: bool
    message: str


class InitAdminRequest(BaseModel):
    user: str = Field(..., min_length=2, description="Tên tài khoản quản trị viên")
    password: str = Field(..., min_length=4, description="Mật khẩu")
    email: str = Field(..., description="Email quản trị viên")
    phone: str | None = Field(None, description="Số điện thoại")
    full_name: str | None = None


class UserResponseSchema(BaseModel):
    user: str
    password: str
    email: str
    phone: str | None = None
    role: str
    user_id: str | None = None
    full_name: str | None = None
    title: str | None = None
    is_active: bool = True


class CreateUserRequest(BaseModel):
    user: str = Field(..., min_length=2, description="Tên tài khoản")
    password: str = Field(..., min_length=4, description="Mật khẩu")
    email: str = Field(..., description="Email người dùng")
    phone: str | None = Field(None, description="Số điện thoại")
    role: str = Field("SALE", description="Vai trò: ADMIN, MANAGER, SALE, POLICY_ADMIN")
    full_name: str | None = None


class UpdateUserRequest(BaseModel):
    password: str | None = None
    email: str | None = None
    phone: str | None = None
    role: str | None = None
    full_name: str | None = None
    title: str | None = None
    is_active: bool | None = None


def _format_user(u: UserModel) -> dict[str, Any]:
    return {
        "user": u.user,
        "password": u.password,
        "email": u.email,
        "phone": u.phone or "",
        "role": u.role,
        # Trường tương thích ngược
        "user_id": u.user,
        "full_name": u.user,
        "title": u.role,
        "is_active": True,
    }


# -----------------------------------------------------------------------------
# Endpoints Khởi tạo ban đầu (First-time Admin Setup)
# -----------------------------------------------------------------------------
@router.get("/setup-status", response_model=SetupStatusResponse)
async def get_setup_status(db: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    """Kiểm tra xem hệ thống đã có tài khoản Quản trị viên (ADMIN) chưa."""
    total_users = await db.scalar(select(func.count(UserModel.user))) or 0
    admin_count = (
        await db.scalar(
            select(func.count(UserModel.user)).where(UserModel.role == "ADMIN")
        )
        or 0
    )
    initialized = admin_count > 0

    return {
        "initialized": initialized,
        "total_users": total_users,
        "has_admin": initialized,
        "message": "Hệ thống đã có Quản trị viên" if initialized else "Chưa có Quản trị viên. Cần khởi tạo tài khoản đầu tiên.",
    }


@router.post("/setup", status_code=status.HTTP_201_CREATED)
async def init_admin_account(
    req: InitAdminRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Khởi tạo tài khoản Quản trị viên ban đầu (CHỈ CHO PHÉP 1 LẦN DUY NHẤT)."""
    admin_count = (
        await db.scalar(
            select(func.count(UserModel.user)).where(UserModel.role == "ADMIN")
        )
        or 0
    )
    if admin_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hệ thống đã có Quản trị viên (ADMIN). Không thể thực hiện khởi tạo lại.",
        )

    user_name = (req.user or req.full_name or "admin").strip()
    email_clean = str(req.email).strip().lower()

    existing_user = await db.scalar(
        select(UserModel).where(
            (func.lower(UserModel.user) == user_name.lower())
            | (func.lower(UserModel.email) == email_clean)
        )
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tài khoản '{user_name}' hoặc email '{email_clean}' đã được sử dụng.",
        )

    new_admin = UserModel(
        user=user_name,
        password=hash_md5(req.password),
        email=email_clean,
        phone=req.phone.strip() if req.phone else None,
        role="ADMIN",
    )
    db.add(new_admin)
    await db.commit()
    await db.refresh(new_admin)

    token = create_access_token(new_admin.user, new_admin.role)
    expires_at = (datetime.now(UTC) + timedelta(hours=8)).isoformat()
    user_data = _format_user(new_admin)

    return {
        "status": "success",
        "message": "Khởi tạo tài khoản Quản trị viên đầu tiên thành công!",
        "access_token": token,
        "expires_at": expires_at,
        "user": user_data,
    }


# -----------------------------------------------------------------------------
# Endpoints Quản trị Users (Dành riêng cho ADMIN)
# -----------------------------------------------------------------------------
@router.get("/users", response_model=list[UserResponseSchema])
async def list_users(
    role: str | None = Query(None),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> list[dict[str, Any]]:
    """Lấy danh sách người dùng trong hệ thống (Yêu cầu quyền ADMIN)."""
    if principal.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Quản trị viên (ADMIN) mới có quyền truy cập trang quản trị.",
        )

    stmt = select(UserModel).order_by(UserModel.user.asc())
    if role:
        stmt = stmt.where(UserModel.role == role.upper())
    if search:
        kw = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            func.lower(UserModel.user).like(kw)
            | func.lower(UserModel.email).like(kw)
            | func.lower(UserModel.phone).like(kw)
        )

    users = (await db.scalars(stmt)).all()
    return [_format_user(u) for u in users]


@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=UserResponseSchema)
async def create_user(
    req: CreateUserRequest,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """Tạo người dùng mới (Yêu cầu quyền ADMIN)."""
    if principal.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Quản trị viên (ADMIN) mới có quyền thêm người dùng.",
        )

    user_name = (req.user or req.full_name or "").strip()
    if not user_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên người dùng (user) không được để trống.",
        )

    email_clean = str(req.email).strip().lower()
    existing = await db.scalar(
        select(UserModel).where(
            (func.lower(UserModel.user) == user_name.lower())
            | (func.lower(UserModel.email) == email_clean)
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tài khoản '{user_name}' hoặc email '{email_clean}' đã tồn tại trong hệ thống.",
        )

    role_clean = req.role.strip().upper()
    valid_roles = {"ADMIN", "MANAGER", "SALE", "POLICY_ADMIN"}
    if role_clean not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Vai trò không hợp lệ. Phải là một trong: {', '.join(valid_roles)}",
        )

    new_user = UserModel(
        user=user_name,
        password=hash_md5(req.password),
        email=email_clean,
        phone=req.phone.strip() if req.phone else None,
        role=role_clean,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return _format_user(new_user)


@router.put("/users/{user_id}", response_model=UserResponseSchema)
async def update_user(
    user_id: str,
    req: UpdateUserRequest,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """Cập nhật thông tin, phân quyền, hoặc đổi mật khẩu user (Yêu cầu quyền ADMIN)."""
    if principal.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Quản trị viên (ADMIN) mới có quyền chỉnh sửa người dùng.",
        )

    user = await db.scalar(select(UserModel).where(UserModel.user == user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy người dùng '{user_id}'.",
        )

    if req.email is not None:
        user.email = req.email.strip().lower()
    if req.phone is not None:
        user.phone = req.phone.strip() if req.phone else None
    if req.role is not None:
        new_role = req.role.strip().upper()
        valid_roles = {"ADMIN", "MANAGER", "SALE", "POLICY_ADMIN"}
        if new_role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Vai trò không hợp lệ. Phải là một trong: {', '.join(valid_roles)}",
            )
        user.role = new_role
    if req.password:
        user.password = hash_md5(req.password)

    await db.commit()
    await db.refresh(user)
    return _format_user(user)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """Xóa tài khoản người dùng (Yêu cầu quyền ADMIN)."""
    if principal.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Quản trị viên (ADMIN) mới có quyền xóa người dùng.",
        )

    user = await db.scalar(select(UserModel).where(UserModel.user == user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy người dùng '{user_id}'.",
        )

    # Chặn tự xóa chính mình hoặc xóa Admin cuối cùng
    if user.user == principal.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tự xóa tài khoản của chính mình.",
        )

    if user.role == "ADMIN":
        admin_count = (
            await db.scalar(
                select(func.count(UserModel.user)).where(UserModel.role == "ADMIN")
            )
            or 0
        )
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không thể xóa tài khoản Quản trị viên duy nhất còn lại trong hệ thống.",
            )

    await db.delete(user)
    await db.commit()
    return {"status": "success", "message": f"Đã xóa người dùng {user_id}."}
