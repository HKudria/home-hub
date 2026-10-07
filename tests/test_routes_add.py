import io, json, pytest
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient
from app.db import init_db
from app.services.medicine_service import MedicineService
from app.web.app_factory import create_test_app

def png():
    return io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 64)

@pytest.mark.asyncio
async def test_add_manual(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    app = create_test_app(conn, data_dir=str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/add", data={"name": "A", "quantity": "5", "expiry_date": "2027-01-01"},
                         follow_redirects=True)
        assert r.status_code == 200
    rows = conn.execute("SELECT * FROM medicines").fetchall()
    assert rows[0]["name"] == "A" and rows[0]["ai_status"] == "ok"

@pytest.mark.asyncio
async def test_add_requires_expiry(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    app = create_test_app(conn, data_dir=str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/add", data={"name": "A", "quantity": "5", "expiry_date": ""})
    assert r.status_code == 400
    assert conn.execute("SELECT COUNT(*) c FROM medicines").fetchone()["c"] == 0

@pytest.mark.asyncio
async def test_extract_multiple_packages(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    app = create_test_app(conn, data_dir=str(tmp_path))
    fake = AsyncMock(return_value=AsyncMock(name="", multiple=True, expiry_date=None,
                          active_ingredient="", form="",
                          dosage_pl="", dosage_ru="", dosage_uk="", dosage_en="",
                          description_pl="", description_ru="", description_uk="", description_en=""))
    with patch("app.web.routes.extract_medicine", fake):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.post("/extract", files=[("images", ("a.jpg", png(), "image/jpeg"))])
    assert json.loads(r.text) == {"multiple": True}

@pytest.mark.asyncio
async def test_extract_with_mocked_ai(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    app = create_test_app(conn, data_dir=str(tmp_path))
    fake_extract = AsyncMock(return_value=None)
    ext = AsyncMock(multiple=False, expiry_date="2027-01-01",
                    active_ingredient="", form="",
                    dosage_pl="", dosage_ru="", dosage_uk="", dosage_en="",
                    description_pl="", description_ru="", description_uk="", description_en="")
    ext.name = "X"
    fake_extract.return_value = ext
    with patch("app.web.routes.extract_medicine", fake_extract):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.post("/extract", files=[("images", ("a.jpg", png(), "image/jpeg"))])
    assert r.status_code == 200
    assert json.loads(r.text)["name"] == "X"

@pytest.mark.asyncio
async def test_take_dose_route(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    mid = MedicineService(conn).add({"name": "A", "quantity": 10})
    app = create_test_app(conn, data_dir=str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(f"/medicine/{mid}/take", data={"amount": "2"}, follow_redirects=True)
    assert r.status_code == 200
    assert conn.execute("SELECT quantity FROM medicines WHERE id=?", (mid,)).fetchone()["quantity"] == 8

@pytest.mark.asyncio
async def test_edit_medicine(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    mid = MedicineService(conn).add({"name": "A", "quantity": 2, "expiry_date": "2026-01-01"})
    app = create_test_app(conn, data_dir=str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(f"/medicine/{mid}/edit",
                         data={"name": "A2", "expiry_date": "2027-02-02", "quantity": "9",
                               "unit": "pieces", "low_stock_threshold": "3"},
                         follow_redirects=True)
        assert r.status_code == 200
    row = conn.execute("SELECT * FROM medicines WHERE id=?", (mid,)).fetchone()
    assert row["name"] == "A2" and row["quantity"] == 9 and row["expiry_date"] == "2027-02-02"

@pytest.mark.asyncio
async def test_edit_rejects_partial_expiry(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    mid = MedicineService(conn).add({"name": "A", "expiry_date": "2026-01-01"})
    app = create_test_app(conn, data_dir=str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(f"/medicine/{mid}/edit",
                         data={"name": "A", "expiry_date": "2027-03"})
    assert r.status_code == 400
    assert conn.execute("SELECT expiry_date FROM medicines WHERE id=?",
                        (mid,)).fetchone()["expiry_date"] == "2026-01-01"

@pytest.mark.asyncio
async def test_edit_missing_404(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    app = create_test_app(conn, data_dir=str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/medicine/999/edit",
                         data={"name": "A", "expiry_date": "2027-02-02"})
        assert r.status_code == 404
        r = await c.get("/medicine/999/edit")
        assert r.status_code == 404
