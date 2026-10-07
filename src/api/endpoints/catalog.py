"""
REST API endpoints cho Danh mục Dự án, Giỏ căn hộ và Xác thực (AP-09 / Catalog & Auth).
Cung cấp dữ liệu thực tế cho Frontend UI (Customer & Internal) kết nối trực tiếp.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import Principal, create_access_token, get_current_principal
from src.contracts.units import BEDROOMS_BY_UNIT_TYPE, merge_units
from src.db.models import ProjectModel, UnitModel, UserModel
from src.db.session import get_db_session
from src.services import data_source, policy_source

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["catalog-auth"])

# -----------------------------------------------------------------------------
# Fixture / Persistent Data cho Dự án & Căn hộ
# -----------------------------------------------------------------------------
PROJECTS_DATA = [
    {
        "project_id": "THE_ZEN_PARK",
        "name": "The Zen Park",
        "location": "Phường Long Thạnh Mỹ, TP. Thủ Đức, TP. HCM",
        "description": "Khu căn hộ xanh 3 toà tháp bên hồ cảnh quan 2,5ha, tiện ích nội khu chuẩn resort, kết nối trực tiếp Vành đai 3.",
        "handover_time": "Quý IV/2027",
    },
    {
        "project_id": "VLANDFUTURE_SAPPHIRE",
        "name": "VLandFuture Sapphire",
        "location": "Phường Tân Phong, Quận 7, TP. HCM",
        "description": "Tổ hợp căn hộ cao cấp ven sông Sài Gòn, 2 toà tháp 35 tầng, hồ bơi vô cực tầng thượng và bến du thuyền riêng.",
        "handover_time": "Quý II/2028",
    },
]

UNITS_DATA = [
    {
        "unit_code": "ZEN-A-1205",
        "project_id": "THE_ZEN_PARK",
        "project_name": "The Zen Park",
        "block": "Tòa A",
        "floor": 12,
        "bedrooms": 2,
        "area_m2": 72.5,
        "view": "View hồ cảnh quan",
        "listed_price_before_tax_vnd": 4_200_000_000,
        "status": "AVAILABLE",
    },
    {
        "unit_code": "ZEN-A-0803",
        "project_id": "THE_ZEN_PARK",
        "project_name": "The Zen Park",
        "block": "Tòa A",
        "floor": 8,
        "bedrooms": 1,
        "area_m2": 52.0,
        "view": "View nội khu",
        "listed_price_before_tax_vnd": 2_500_000_000,
        "status": "AVAILABLE",
    },
    {
        "unit_code": "ZEN-A-1810",
        "project_id": "THE_ZEN_PARK",
        "project_name": "The Zen Park",
        "block": "Tòa A",
        "floor": 18,
        "bedrooms": 2,
        "area_m2": 75.0,
        "view": "View hồ cảnh quan",
        "listed_price_before_tax_vnd": 4_450_000_000,
        "status": "SOLD",
    },
    {
        "unit_code": "ZEN-B-1502",
        "project_id": "THE_ZEN_PARK",
        "project_name": "The Zen Park",
        "block": "Tòa B",
        "floor": 15,
        "bedrooms": 3,
        "area_m2": 98.2,
        "view": "View trực diện hồ cảnh quan",
        "listed_price_before_tax_vnd": 6_100_000_000,
        "status": "AVAILABLE",
    },
    {
        "unit_code": "SAP-01-2204",
        "project_id": "VLANDFUTURE_SAPPHIRE",
        "project_name": "VLandFuture Sapphire",
        "block": "Sapphire 1",
        "floor": 22,
        "bedrooms": 2,
        "area_m2": 81.0,
        "view": "View sông Sài Gòn",
        "listed_price_before_tax_vnd": 5_800_000_000,
        "status": "AVAILABLE",
    },
]

STAFF_USERS = [
    {
        "user_id": "USR-SALE-001",
        "full_name": "Hoàng Nam",
        "email": "nam.hoang@vlandfuture.vn",
        "phone": "0903 123 456",
        "role": "SALE",
        "title": "Chuyên viên kinh doanh",
    },
    {
        "user_id": "USR-MGR-001",
        "full_name": "Hà Nguyễn",
        "email": "ha.nguyen@vlandfuture.vn",
        "phone": "0909 555 010",
        "role": "MANAGER",
        "title": "Quản lý kinh doanh",
    },
    {
        "user_id": "USR-ADM-001",
        "full_name": "Tuấn Minh",
        "email": "minh.tuan@vlandfuture.vn",
        "phone": "0912 000 321",
        "role": "POLICY_ADMIN",
        "title": "Chuyên viên quản trị chính sách",
    },
]

# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------
class ProjectSchema(BaseModel):
    project_id: str
    name: str
    location: str
    description: str
    handover_time: str

class PromotionItem(BaseModel):
    title: str
    section: str

class PolicySnapshotRefSchema(BaseModel):
    policy_id: str
    policy_version: int
    content_sha256: str

class ProjectOverviewSchema(BaseModel):
    project: ProjectSchema
    active_policy: PolicySnapshotRefSchema | None = None
    promotions: list[PromotionItem] = Field(default_factory=list)
    available_units: int = 0
    price_from_vnd: int | None = None

class UnitSnapshotSchema(BaseModel):
    unit_code: str
    project_id: str
    project_name: str
    block: str
    floor: int
    bedrooms: int
    area_m2: float
    view: str
    listed_price_before_tax_vnd: int
    status: str

class StaffUserSchema(BaseModel):
    user_id: str
    full_name: str
    role: str
    email: str
    phone: str
    title: str

class LoginRequest(BaseModel):
    email: str
    password: str

class AuthSessionSchema(BaseModel):
    access_token: str
    expires_at: str
    user: StaffUserSchema

class ReauthRequest(BaseModel):
    password: str

class ReauthGrantSchema(BaseModel):
    reauth_token: str
    expires_at: str

# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
def _unit_model_to_dict(u: UnitModel, project_name: str | None = None) -> dict[str, Any]:
    """Chuyển 1 dòng `units` trong DB thành payload API.

    Chỉ trả những trường DB **thật sự lưu** (mã căn, dự án, tầng, loại căn, giá, trạng thái).
    Trước đây hàm này tự "đoán" diện tích theo loại căn (2BR → 72.0m²), gán tháp/view theo tiền tố mã căn
    và **hardcode tên dự án "VLand Future Riverside"** — Sale sẽ đọc số sai đó cho khách. Nay `area_m2` và
    `view` là **cột thật của bảng `units`** (đợt 20); căn nào chưa điền thì trả 0/chuỗi rỗng để UI hiện "—",
    không suy diễn. Tên dự án lấy từ bảng `projects` (ưu tiên tham số truyền vào).
    """
    return {
        "unit_code": u.unit_code,
        "project_id": u.project_id,
        "project_name": project_name or u.project_id,
        "floor": u.floor_number,
        "bedrooms": BEDROOMS_BY_UNIT_TYPE.get(str(u.unit_type or "").upper(), 0),
        "area_m2": float(u.area_m2) if u.area_m2 else 0.0,
        "listed_price_before_tax_vnd": u.listed_price_before_tax_vnd,
        "status": u.status,
        # `block` (tên tháp) KHÔNG có trong bảng `units`; trả rỗng thay vì suy diễn theo mã căn.
        "block": "",
        # `view` là cột thật của bảng `units` (đợt 20); chưa điền thì trả chuỗi rỗng để UI hiện "—".
        "view": str(u.view or "").strip(),
    }


@router.get("/public/projects", response_model=list[ProjectOverviewSchema])
async def get_public_projects(
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """GET /api/v1/public/projects — Trang chủ khách hàng & danh mục dự án (nguồn: CSDL thật).

    Fixture chỉ tham gia khi bật `ALLOW_FIXTURE_DATA` (test/demo offline).
    """
    overviews: list[dict[str, Any]] = []

    # 1. Dự án THẬT từ DB: tên lấy từ bảng `projects`, số căn mở bán đếm theo bảng `units`.
    #    Không gán vị trí/mô tả/khuyến mãi cho dự án khi DB không có dữ liệu đó.
    project_rows = (await db.scalars(select(ProjectModel))).all()
    project_names = {p.project_id: p.project_name for p in project_rows}
    db_units = (await db.scalars(select(UnitModel))).all()
    db_project_ids = list(dict.fromkeys(u.project_id for u in db_units))
    for pid in db_project_ids:
        group = [u for u in db_units if u.project_id == pid]
        available = [u for u in group if u.status == "AVAILABLE"]
        price_from = min([u.listed_price_before_tax_vnd for u in available]) if available else None
        overviews.append({
            "project": {
                "project_id": pid,
                "name": project_names.get(pid) or pid,
                "location": "",
                "description": "",
                "handover_time": "",
            },
            "active_policy": None,
            "promotions": [],
            "available_units": len(available),
            "price_from_vnd": price_from,
        })

    # 2. Dự án chỉ có trong fixture — CHỈ khi bật `ALLOW_FIXTURE_DATA` (test/demo offline).
    #    Chạy thật: không có căn trong DB thì dự án cũng không hiện, tuyệt đối không đưa dự án mẫu ra
    #    cho khách xem (trước đây nhánh này luôn chạy nên trang khách có dự án/căn không có trong CSDL).
    for proj in (PROJECTS_DATA if data_source.fixtures_allowed() else []):
        pid = proj["project_id"]
        if pid in db_project_ids:
            continue
        units = [u for u in UNITS_DATA if u["project_id"] == pid and u["status"] == "AVAILABLE"]
        price_from = min([u["listed_price_before_tax_vnd"] for u in units]) if units else None
        overviews.append({
            "project": proj,
            "active_policy": {
                "policy_id": "POL-2026-EARLY",
                "policy_version": 1,
                "content_sha256": "3e23cf6329e46939fc9f6ab43a9b6c039f60bc9f9f83a45c38bc35718dfb5722",
            },
            "promotions": [
                {"title": "Chiết khấu thanh toán sớm 95% (8.0%)", "section": "Điều 1"},
                {"title": "Hỗ trợ lãi suất 0% trong 24 tháng", "section": "Điều 2"},
                {"title": "Gói quà tặng nội thất cao cấp 200tr", "section": "Điều 3"},
            ],
            "available_units": len(units),
            "price_from_vnd": price_from,
        })
    return overviews


@router.get("/units", response_model=list[UnitSnapshotSchema])
async def get_units(
    project_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """GET /api/v1/units — Giỏ hàng căn hộ đọc từ CSDL thật (fixture chỉ khi bật cờ test/demo)."""
    stmt = select(UnitModel)
    if project_id and project_id not in ("ALL", ""):
        stmt = stmt.where(UnitModel.project_id == project_id)

    db_units = (await db.scalars(stmt)).all()
    project_rows = (await db.scalars(select(ProjectModel))).all()
    project_names = {p.project_id: p.project_name for p in project_rows}
    converted_db_units = [_unit_model_to_dict(u, project_names.get(u.project_id)) for u in db_units]

    scoped_fixture = [
        u
        for u in (UNITS_DATA if data_source.fixtures_allowed() else [])
        if not project_id or project_id in ("ALL", "") or u["project_id"] == project_id
    ]
    # Cùng một luật gộp với lớp Copilot: CSDL là nguồn duy nhất, fixture chỉ được bù (dự án DB chưa có)
    # khi bật `ALLOW_FIXTURE_DATA` — trước đây fixture luôn được trộn nên Sale thấy căn demo trong giỏ thật.
    return merge_units(converted_db_units, scoped_fixture)


@router.post("/auth/login", response_model=AuthSessionSchema)
async def auth_login(
    req: LoginRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """POST /api/v1/auth/login — Đăng nhập nhân sự từ DB thật (MD5 hash). Hỗ trợ tài khoản (user) hoặc email."""
    account_input = req.email.strip().lower()

    # 1. Tìm user trong DB thật theo tài khoản (user) hoặc email
    user_db = await db.scalar(
        select(UserModel).where(
            (func.lower(UserModel.user) == account_input)
            | (func.lower(UserModel.email) == account_input)
        )
    )
    if not user_db:
        # Kiểm tra xem hệ thống có user nào chưa
        total_users = await db.scalar(select(func.count(UserModel.user))) or 0
        if total_users == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hệ thống chưa có tài khoản nào. Vui lòng truy cập /admin_cp để khởi tạo Quản trị viên đầu tiên.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản hoặc email không tồn tại trong hệ thống cơ sở dữ liệu.",
        )

    # 2. Khớp mật khẩu MD5 trực tiếp với giá trị lưu trong CSDL thật
    req_hash = hashlib.md5(req.password.strip().encode("utf-8")).hexdigest()
    if req_hash != user_db.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mật khẩu không chính xác.",
        )

    token = create_access_token(user_db.user, user_db.role)
    expires_at = (datetime.now(UTC) + timedelta(hours=8)).isoformat()
    return {
        "access_token": token,
        "expires_at": expires_at,
        "user": {
            "user_id": user_db.user,
            "full_name": user_db.user,
            "email": user_db.email,
            "phone": user_db.phone or "",
            "role": user_db.role,
            "title": user_db.role,
        },
    }


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def auth_logout():
    """POST /api/v1/auth/logout — Đăng xuất."""
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/auth/reauth", response_model=ReauthGrantSchema)
async def auth_reauth(
    req: ReauthRequest,
    db: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(get_current_principal),
) -> dict[str, Any]:
    """POST /api/v1/auth/reauth — Xác thực lại trước khi ký duyệt HITL (TD-4.1)."""
    user_db = await db.scalar(
        select(UserModel).where(
            (UserModel.user == principal.user_id)
            | (UserModel.email == principal.user_id)
        )
    )
    if user_db:
        req_hash = hashlib.md5(req.password.strip().encode("utf-8")).hexdigest()
        if req_hash != user_db.password:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Mật khẩu xác thực lại không chính xác.",
            )

    token = f"reauth_{secrets.token_hex(16)}"
    expires_at = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
    return {
        "reauth_token": token,
        "expires_at": expires_at,
    }



# -----------------------------------------------------------------------------
# Fixture & Endpoints cho Chính sách Bán hàng (Policies)
# -----------------------------------------------------------------------------
POLICIES_DATA: list[dict[str, Any]] = [
    {
        "policy_id": "CSBH-ZEN-2026-V2.0",
        "policy_version": "v2.0",
        "title": "Chính sách Bán hàng The Zen Park — Đợt 2/2026",
        "project_id": "THE_ZEN_PARK",
        "status": "EXPIRED",
        "effective_from": "2026-05-01",
        "effective_to": "2026-07-31",
        "document_id": "DOC-ZEN-2026-02",
        "document_hash": "2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f90123456789abcdef0123456789abc",
        "source_document": "CSBH_TheZenPark_2026_V2_Signed.pdf",
        "created_at": "2026-04-25T08:00:00Z",
        "created_by": {"user_id": "USR-ADM-001", "full_name": "Tuấn Minh", "role": "POLICY_ADMIN"},
        "published_at": "2026-04-30T10:00:00Z",
        "published_by": {"user_id": "USR-MGR-001", "full_name": "Nguyễn Văn Quản Lý", "role": "MANAGER"},
        "rules": [
            {
                "rule_code": "RESIDENT_DISCOUNT",
                "title": "Chiết khấu cư dân tri ân",
                "kind": "PERCENT_DISCOUNT",
                "discount_rate": 0.015,
                "cash_equivalent_vnd": None,
                "interest_support_months": None,
                "applicable_scenarios": ["PA-CHUDONG", "PA-NHANH", "PA-VAY"],
                "required_segments": ["EXISTING_RESIDENT"],
                "min_units_purchased": None,
                "relations": [],
                "is_ambiguous": False,
                "is_selectable": False,
                "validation_status": "APPROVED_FOR_USE",
                "source": {
                    "document_id": "DOC-ZEN-2026-02",
                    "document_version": "v2.0",
                    "document_hash": "2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f90123456789abcdef0123456789abc",
                    "clause_id": "Dieu_2_Khoan_1",
                    "section": "Điều 2, Khoản 1",
                    "page": 2,
                    "quote": "Khách hàng là cư dân hiện hữu của VLandFuture có hợp đồng mua bán hợp lệ trước đó được hưởng chiết khấu tri ân 1.5% trên Giá bán chưa bao gồm thuế GTGT và KPBT.",
                },
            },
            {
                "rule_code": "EARLY_PAY_DISCOUNT",
                "title": "Chiết khấu thanh toán sớm 95% (V2.0)",
                "kind": "PERCENT_DISCOUNT",
                "discount_rate": 0.07,
                "cash_equivalent_vnd": None,
                "interest_support_months": None,
                "applicable_scenarios": ["PA-NHANH"],
                "required_segments": None,
                "min_units_purchased": None,
                "relations": [
                    {"type": "MUTUALLY_EXCLUSIVE", "rule_code": "FURNITURE_GIFT", "reason": "Không áp dụng đồng thời với quà nội thất."},
                    {"type": "CONDITIONAL_CONFLICT", "rule_code": "BANK_LOAN_HTLS", "reason": "Không áp dụng đồng thời gói vay hỗ trợ lãi suất."},
                ],
                "is_ambiguous": False,
                "is_selectable": True,
                "validation_status": "APPROVED_FOR_USE",
                "source": {
                    "document_id": "DOC-ZEN-2026-02",
                    "document_version": "v2.0",
                    "document_hash": "2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f90123456789abcdef0123456789abc",
                    "clause_id": "Dieu_4_Khoan_2b",
                    "section": "Điều 4, Khoản 2b",
                    "page": 4,
                    "quote": "Khách hàng lựa chọn thanh toán sớm 95% bằng vốn tự có trong vòng 15 ngày kể từ ngày ký HĐMB được hưởng chiết khấu 7.0% trên Giá bán chưa bao gồm thuế GTGT và KPBT.",
                },
            },
            {
                "rule_code": "BANK_LOAN_HTLS",
                "title": "Hỗ trợ lãi suất 0% trong 18 tháng (V2.0)",
                "kind": "BANK_SUPPORT",
                "discount_rate": None,
                "cash_equivalent_vnd": None,
                "interest_support_months": 18,
                "applicable_scenarios": ["PA-VAY"],
                "required_segments": None,
                "min_units_purchased": None,
                "relations": [
                    {"type": "CONDITIONAL_CONFLICT", "rule_code": "EARLY_PAY_DISCOUNT", "reason": "Không thể cùng vay ngân hàng và thanh toán sớm bằng vốn tự có."},
                ],
                "is_ambiguous": False,
                "is_selectable": True,
                "validation_status": "APPROVED_FOR_USE",
                "source": {
                    "document_id": "DOC-ZEN-2026-02",
                    "document_version": "v2.0",
                    "document_hash": "2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f90123456789abcdef0123456789abc",
                    "clause_id": "Dieu_3_Khoan_1",
                    "section": "Điều 3, Khoản 1",
                    "page": 3,
                    "quote": "Hỗ trợ lãi suất 0% tối đa 18 tháng hoặc đến khi nhận bàn giao nhà.",
                },
            },
            {
                "rule_code": "FURNITURE_GIFT",
                "title": "Gói quà tặng nội thất cao cấp 150tr (V2.0)",
                "kind": "GIFT",
                "discount_rate": None,
                "cash_equivalent_vnd": 150_000_000,
                "interest_support_months": None,
                "applicable_scenarios": ["PA-CHUDONG", "PA-NHANH", "PA-VAY"],
                "required_segments": None,
                "min_units_purchased": None,
                "relations": [
                    {"type": "MUTUALLY_EXCLUSIVE", "rule_code": "EARLY_PAY_DISCOUNT", "reason": "Không áp dụng đồng thời với chiết khấu thanh toán sớm 95%."},
                ],
                "is_ambiguous": False,
                "is_selectable": True,
                "validation_status": "APPROVED_FOR_USE",
                "source": {
                    "document_id": "DOC-ZEN-2026-02",
                    "document_version": "v2.0",
                    "document_hash": "2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f90123456789abcdef0123456789abc",
                    "clause_id": "Dieu_6_Khoan_2",
                    "section": "Điều 6, Khoản 2",
                    "page": 6,
                    "quote": "Tặng gói nội thất cao cấp trị giá 150 triệu đồng khi ký HĐMB.",
                },
            },
        ],
    },
    {
        "policy_id": "CSBH-ZEN-2026-V3.1",
        "policy_version": "v3.1",
        "title": "Chính sách Bán hàng The Zen Park — Đợt 3/2026",
        "project_id": "THE_ZEN_PARK",
        "status": "ACTIVE",
        "effective_from": "2026-08-01",
        "effective_to": "2026-12-31",
        "document_id": "DOC-ZEN-2026-03",
        "document_hash": "3e23cf6329e46939fc9f6ab43a9b6c039f60bc9f9f83a45c38bc35718dfb5722",
        "source_document": "CSBH_TheZenPark_2026_V3_Signed.pdf",
        "created_at": "2026-07-25T08:00:00Z",
        "created_by": {"user_id": "USR-ADM-001", "full_name": "Tuấn Minh", "role": "POLICY_ADMIN"},
        "published_at": "2026-07-30T10:00:00Z",
        "published_by": {"user_id": "USR-MGR-001", "full_name": "Nguyễn Văn Quản Lý", "role": "MANAGER"},
        "rules": [
            {
                "rule_code": "RESIDENT_DISCOUNT",
                "title": "Chiết khấu cư dân tri ân",
                "kind": "PERCENT_DISCOUNT",
                "discount_rate": 0.015,
                "cash_equivalent_vnd": None,
                "interest_support_months": None,
                "applicable_scenarios": ["PA-CHUDONG", "PA-NHANH", "PA-VAY"],
                "required_segments": ["EXISTING_RESIDENT"],
                "min_units_purchased": None,
                "relations": [],
                "is_ambiguous": False,
                "is_selectable": False,
                "validation_status": "APPROVED_FOR_USE",
                "source": {
                    "document_id": "DOC-ZEN-2026-03",
                    "document_version": "v3.1",
                    "document_hash": "3e23cf6329e46939fc9f6ab43a9b6c039f60bc9f9f83a45c38bc35718dfb5722",
                    "clause_id": "Dieu_2_Khoan_1",
                    "section": "Điều 2, Khoản 1",
                    "page": 2,
                    "quote": "Khách hàng là cư dân hiện hữu của VLandFuture có hợp đồng mua bán hợp lệ trước đó được hưởng chiết khấu tri ân 1.5% trên Giá bán chưa bao gồm thuế GTGT và KPBT.",
                },
            },
            {
                "rule_code": "EARLY_PAY_DISCOUNT",
                "title": "Chiết khấu thanh toán sớm 95%",
                "kind": "PERCENT_DISCOUNT",
                "discount_rate": 0.08,
                "cash_equivalent_vnd": None,
                "interest_support_months": None,
                "applicable_scenarios": ["PA-NHANH"],
                "required_segments": None,
                "min_units_purchased": None,
                "relations": [
                    {"type": "MUTUALLY_EXCLUSIVE", "rule_code": "FURNITURE_GIFT", "reason": "Điều 6, Khoản 2: không áp dụng đồng thời với quà nội thất."},
                    {"type": "CONDITIONAL_CONFLICT", "rule_code": "BANK_LOAN_HTLS", "reason": "Không áp dụng đồng thời gói vay hỗ trợ lãi suất."},
                ],
                "is_ambiguous": False,
                "is_selectable": True,
                "validation_status": "APPROVED_FOR_USE",
                "source": {
                    "document_id": "DOC-ZEN-2026-03",
                    "document_version": "v3.1",
                    "document_hash": "3e23cf6329e46939fc9f6ab43a9b6c039f60bc9f9f83a45c38bc35718dfb5722",
                    "clause_id": "Dieu_4_Khoan_2b",
                    "section": "Điều 4, Khoản 2b",
                    "page": 4,
                    "quote": "Khách hàng lựa chọn thanh toán sớm 95% bằng vốn tự có trong vòng 15 ngày kể từ ngày ký HĐMB được hưởng chiết khấu 8.0% trên Giá bán chưa bao gồm thuế GTGT và KPBT.",
                },
            },
            {
                "rule_code": "BANK_LOAN_HTLS",
                "title": "Hỗ trợ lãi suất 0% trong 24 tháng",
                "kind": "BANK_SUPPORT",
                "discount_rate": None,
                "cash_equivalent_vnd": None,
                "interest_support_months": 24,
                "applicable_scenarios": ["PA-VAY"],
                "required_segments": None,
                "min_units_purchased": None,
                "relations": [
                    {"type": "CONDITIONAL_CONFLICT", "rule_code": "EARLY_PAY_DISCOUNT", "reason": "Không thể cùng vay ngân hàng và thanh toán sớm bằng vốn tự có."},
                ],
                "is_ambiguous": False,
                "is_selectable": True,
                "validation_status": "APPROVED_FOR_USE",
                "source": {
                    "document_id": "DOC-ZEN-2026-03",
                    "document_version": "v3.1",
                    "document_hash": "3e23cf6329e46939fc9f6ab43a9b6c039f60bc9f9f83a45c38bc35718dfb5722",
                    "clause_id": "Dieu_3_Khoan_1",
                    "section": "Điều 3, Khoản 1",
                    "page": 3,
                    "quote": "Hỗ trợ lãi suất 0% tối đa 24 tháng hoặc đến khi nhận bàn giao nhà.",
                },
            },
            {
                "rule_code": "FURNITURE_GIFT",
                "title": "Gói quà tặng nội thất cao cấp 200tr",
                "kind": "GIFT",
                "discount_rate": None,
                "cash_equivalent_vnd": 200_000_000,
                "interest_support_months": None,
                "applicable_scenarios": ["PA-CHUDONG", "PA-NHANH", "PA-VAY"],
                "required_segments": None,
                "min_units_purchased": None,
                "relations": [
                    {"type": "MUTUALLY_EXCLUSIVE", "rule_code": "EARLY_PAY_DISCOUNT", "reason": "Điều 6, Khoản 2: không áp dụng đồng thời với chiết khấu thanh toán sớm 95%."},
                ],
                "is_ambiguous": False,
                "is_selectable": True,
                "validation_status": "APPROVED_FOR_USE",
                "source": {
                    "document_id": "DOC-ZEN-2026-03",
                    "document_version": "v3.1",
                    "document_hash": "3e23cf6329e46939fc9f6ab43a9b6c039f60bc9f9f83a45c38bc35718dfb5722",
                    "clause_id": "Dieu_6_Khoan_2",
                    "section": "Điều 6, Khoản 2",
                    "page": 6,
                    "quote": "Tặng gói nội thất cao cấp trị giá 200 triệu đồng khi ký HĐMB.",
                },
            },
        ],
    },
    {
        "policy_id": "CSBH-SAPPHIRE-2026-V1.0",
        "policy_version": "v1.0",
        "title": "Chính sách Bán hàng VLandFuture Sapphire — Mở bán Đợt 1",
        "project_id": "VLANDFUTURE_SAPPHIRE",
        "status": "ACTIVE",
        "effective_from": "2026-01-01",
        "effective_to": "2026-12-31",
        "document_id": "DOC-SAP-2026-01",
        "document_hash": "a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0",
        "source_document": "CSBH_Sapphire_2026_V1.pdf",
        "created_at": "2026-01-01T08:00:00Z",
        "created_by": {"user_id": "USR-ADM-001", "full_name": "Tuấn Minh", "role": "POLICY_ADMIN"},
        "published_at": "2026-01-05T09:00:00Z",
        "published_by": {"user_id": "USR-MGR-001", "full_name": "Nguyễn Văn Quản Lý", "role": "MANAGER"},
        "rules": [
            {
                "rule_code": "SAPPHIRE_EARLY_PAY",
                "title": "Chiết khấu thanh toán sớm 95% (8.0%)",
                "kind": "PERCENT_DISCOUNT",
                "discount_rate": 0.08,
                "cash_equivalent_vnd": None,
                "interest_support_months": None,
                "applicable_scenarios": ["PA-NHANH"],
                "required_segments": None,
                "min_units_purchased": None,
                "relations": [],
                "is_ambiguous": False,
                "is_selectable": True,
                "validation_status": "APPROVED_FOR_USE",
                "source": {
                    "document_id": "DOC-SAP-2026-01",
                    "document_version": "v1.0",
                    "document_hash": "a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0",
                    "clause_id": "Dieu_1",
                    "section": "Điều 1",
                    "page": 1,
                    "quote": "Chiết khấu thanh toán sớm 95% nhận ngay 8.0%.",
                },
            },
        ],
    },
]


async def fetch_db_policies() -> list[dict[str, Any]]:
    """Đọc chính sách THẬT từ CSDL (bảng `policies` + `policy_atoms`).

    Việc dựng rule từ atom nằm ở `src/services/policy_source.py` — **cùng một hàm** với đường Copilot
    đọc (sync), nên trang Chính sách và Copilot không thể lệch số liệu nhau nữa.
    """
    try:
        from sqlalchemy import text

        from src.db.session import async_session_factory

        async with async_session_factory() as session:
            policy_rows = (await session.execute(text(policy_source.POLICY_SQL))).fetchall()
            atom_rows = (await session.execute(text(policy_source.ATOM_SQL))).fetchall()
        return policy_source.policies_from_async_rows(policy_rows, atom_rows)
    except Exception as e:
        logger.error("Error fetching policies from DB: %s", e)
        return []


@router.get("/policies")
async def get_policies(
    project_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
) -> list[dict[str, Any]]:
    """GET /api/v1/policies — Danh sách chính sách bán hàng thật từ CSDL PostgreSQL."""
    db_policies = await fetch_db_policies()
    result = db_policies
    if project_id:
        result = [p for p in result if p["project_id"] == project_id]
    if status_filter:
        result = [p for p in result if p["status"] == status_filter]
    return sorted(result, key=lambda p: p.get("effective_from", ""), reverse=True)


@router.get("/policies/active")
async def get_active_policy(
    project_id: str = Query(...),
    date: str | None = Query(None),
) -> dict[str, Any] | None:
    """GET /api/v1/policies/active — Chính sách có hiệu lực tại thời điểm ngày tra cứu từ CSDL."""
    target_date = date or datetime.now(UTC).strftime("%Y-%m-%d")
    db_policies = await fetch_db_policies()
    for p in db_policies:
        if (p["project_id"] == project_id or project_id == "PROJECT-VLF-001") and p["status"] in ("ACTIVE", "PUBLISHED"):
            if p["effective_from"] <= target_date <= p["effective_to"]:
                return p
    return next((p for p in db_policies if p["project_id"] == project_id), None)


@router.get("/policies/{policy_id}")
async def get_policy_detail(policy_id: str) -> dict[str, Any]:
    """GET /api/v1/policies/{policy_id} — Chi tiết chính sách bán hàng thật từ CSDL."""
    db_policies = await fetch_db_policies()
    for p in db_policies:
        if p["policy_id"] == policy_id:
            return p
    raise HTTPException(status_code=404, detail=f"Chính sách {policy_id} không tồn tại trong CSDL.")


