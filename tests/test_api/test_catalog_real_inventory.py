"""R19 — giỏ hàng/danh mục dự án hiển thị cho Sale phải khớp **DB vận hành**.

Ba lỗi đã gặp ở đợt 19 và được khoá lại bằng test này:
1. "44 căn" = 40 căn DB + 4 căn fixture (cộng trùng hai nguồn, Sale đọc số sai cho khách);
2. dự án "VLand Future Riverside" — tên code gán cứng, không có trong bảng `projects`;
3. API tự suy diễn diện tích theo loại căn ⇒ Sale đọc "98.5m²" cho một căn DB không có số đó.
"""

from __future__ import annotations

from datetime import date

import pytest
import pytest_asyncio

from src.api.endpoints.catalog import UNITS_DATA
from src.db.models import ProjectModel, UnitModel
from tests.conftest import async_test_session_factory

#: Mã dự án vận hành dùng trong bài test (trùng mã của fixture).
PROJECTS = (("THE_ZEN_PARK", "The Zen Park"), ("VLANDFUTURE_SAPPHIRE", "VLandFuture Sapphire"))

#: Mã căn fixture — không được xuất hiện khi DB đã có dữ liệu của chính dự án đó.
FIXTURE_CODES = {str(u["unit_code"]) for u in UNITS_DATA}


def _seed_units() -> list[UnitModel]:
    units: list[UnitModel] = []
    for index in range(20):  # 20 căn The Zen Park
        units.append(
            UnitModel(
                unit_code=f"ZEN-T-{index + 1:04d}",
                project_id="THE_ZEN_PARK",
                unit_type=["1BR", "2BR", "3BR"][index % 3],
                floor_number=5 + index,
                listed_price_before_tax_vnd=3_000_000_000 + index * 150_000_000,
                handover_date=date(2027, 12, 31),
                status="AVAILABLE",
                # Đợt 20: bảng `units` đã có diện tích + view; ca này kiểm chúng đi thẳng ra API.
                area_m2=round(72.0 + (index % 5) * 0.5, 1),
                view="View sông Sài Gòn",
            )
        )
    for index in range(20):  # 20 căn Sapphire, 2 căn đã bán
        units.append(
            UnitModel(
                unit_code=f"SAP-T-{index + 1:04d}",
                project_id="VLANDFUTURE_SAPPHIRE",
                unit_type=["2BR", "3BR"][index % 2],
                floor_number=10 + index,
                listed_price_before_tax_vnd=5_000_000_000 + index * 180_000_000,
                handover_date=date(2027, 12, 31),
                status="SOLD" if index < 2 else "AVAILABLE",
                # Cố ý để trống diện tích/view: ca này kiểm việc API trả 0/rỗng (UI in "—")
                # thay vì suy diễn số theo loại căn.
                area_m2=None,
                view=None,
            )
        )
    return units


@pytest_asyncio.fixture
async def seeded_inventory():
    """Nạp 40 căn vận hành rồi dọn sạch sau test (DB test dùng chung in-memory engine)."""
    units = _seed_units()
    codes = [u.unit_code for u in units]
    async with async_test_session_factory() as session:
        for project_id, name in PROJECTS:
            if await session.get(ProjectModel, project_id) is None:
                session.add(ProjectModel(project_id=project_id, project_name=name, legal_entity_name="VLandFuture"))
        session.add_all(units)
        await session.commit()
    yield
    async with async_test_session_factory() as session:
        for code in codes:
            unit = await session.get(UnitModel, code)
            if unit is not None:
                await session.delete(unit)
        await session.commit()


@pytest.mark.asyncio
async def test_units_endpoint_does_not_double_count_with_fixture(client, seeded_inventory):
    """DB đã có dữ liệu của dự án ⇒ chỉ trả căn DB, không cộng thêm căn fixture (hết cảnh 40 + 4 = 44)."""
    response = await client.get("/api/v1/units")
    assert response.status_code == 200
    units = response.json()
    codes = {u["unit_code"] for u in units}

    assert len([c for c in codes if c.startswith("ZEN-T-")]) == 20
    assert len([c for c in codes if c.startswith("SAP-T-")]) == 20
    assert not (codes & FIXTURE_CODES), "căn fixture không được lẫn vào giỏ khi DB đã có dự án đó"


@pytest.mark.asyncio
async def test_units_endpoint_scoped_by_project_uses_db(client, seeded_inventory):
    """Lọc theo dự án: DB thắng fixture (trước đây nhánh fixture trả về thẳng dữ liệu demo)."""
    response = await client.get("/api/v1/units", params={"project_id": "THE_ZEN_PARK"})
    assert response.status_code == 200
    units = response.json()
    assert units, "phải trả căn từ DB"
    assert {u["unit_code"] for u in units} == {f"ZEN-T-{i + 1:04d}" for i in range(20)}
    assert all(u["project_name"] == "The Zen Park" for u in units)


@pytest.mark.asyncio
async def test_units_payload_has_no_invented_area_or_project_name(client, seeded_inventory):
    """Không suy diễn: căn chưa điền diện tích/view ⇒ 0.0/rỗng; tên dự án lấy từ bảng `projects`."""
    response = await client.get("/api/v1/units", params={"project_id": "VLANDFUTURE_SAPPHIRE"})
    units = response.json()
    assert {u["project_name"] for u in units} == {"VLandFuture Sapphire"}
    assert all(u["area_m2"] == 0.0 for u in units), "chưa có số trong DB thì KHÔNG được suy diễn theo loại căn"
    assert {u["view"] for u in units} == {""}
    assert all("Riverside" not in u["project_name"] for u in units)


@pytest.mark.asyncio
async def test_units_payload_exposes_area_and_view_from_db(client, seeded_inventory):
    """Đợt 20: căn đã có diện tích/view trong DB ⇒ API trả đúng số đó (không bịa, không bỏ trắng)."""
    response = await client.get("/api/v1/units", params={"project_id": "THE_ZEN_PARK"})
    units = response.json()
    assert len(units) == 20
    assert all(u["area_m2"] > 0 for u in units)
    assert {u["view"] for u in units} == {"View sông Sài Gòn"}
    first = next(u for u in units if u["unit_code"] == "ZEN-T-0001")
    assert first["area_m2"] == 72.0


@pytest.mark.asyncio
async def test_public_projects_reads_real_names_and_counts(client, seeded_inventory):
    """Danh mục dự án: tên + số căn mở bán + giá từ lấy từ DB; không gắn khuyến mãi giả."""
    response = await client.get("/api/v1/public/projects")
    assert response.status_code == 200
    overviews = {o["project"]["project_id"]: o for o in response.json()}

    assert "PROJECT-VLF-001" not in overviews, "dự án Riverside không có trong DB thì không được dựng lên"
    zen = overviews["THE_ZEN_PARK"]
    assert zen["project"]["name"] == "The Zen Park"
    assert zen["available_units"] == 20
    assert zen["price_from_vnd"] == 3_000_000_000
    assert zen["promotions"] == [], "không gán khuyến mãi khi DB không có dữ liệu khuyến mãi"
    assert zen["active_policy"] is None, "không gán chính sách khi chưa tra được chính sách thật"

    sapphire = overviews["VLANDFUTURE_SAPPHIRE"]
    assert sapphire["project"]["name"] == "VLandFuture Sapphire"
    assert sapphire["available_units"] == 18, "2 căn SOLD không tính là đang mở bán"


@pytest.mark.asyncio
async def test_units_endpoint_falls_back_to_fixture_when_db_empty(client):
    """DB rỗng (máy dev/môi trường demo) ⇒ vẫn trả giỏ fixture để UI có dữ liệu."""
    response = await client.get("/api/v1/units", params={"project_id": "THE_ZEN_PARK"})
    assert response.status_code == 200
    assert {u["unit_code"] for u in response.json()} <= FIXTURE_CODES


@pytest.mark.asyncio
async def test_units_endpoint_falls_back_to_dash_when_area_or_view_empty(client):
    """Căn chưa điền diện tích/view (DB cũ chưa migrate) ⇒ trả 0/rỗng để UI in "—", không bịa số."""
    import uuid
    from datetime import date as _date

    code = f"NODATA-{uuid.uuid4().hex[:6]}"
    async with async_test_session_factory() as session:
        session.add(
            UnitModel(
                unit_code=code,
                project_id="THE_ZEN_PARK",
                unit_type="2BR",
                floor_number=3,
                listed_price_before_tax_vnd=4_000_000_000,
                handover_date=_date(2027, 12, 31),
                status="AVAILABLE",
                area_m2=None,
                view=None,
            )
        )
        await session.commit()
    try:
        response = await client.get("/api/v1/units", params={"project_id": "THE_ZEN_PARK"})
        assert response.status_code == 200
        unit = next(u for u in response.json() if u["unit_code"] == code)
        assert unit["area_m2"] == 0.0
        assert unit["view"] == ""
    finally:
        async with async_test_session_factory() as session:
            row = await session.get(UnitModel, code)
            if row is not None:
                await session.delete(row)
                await session.commit()
