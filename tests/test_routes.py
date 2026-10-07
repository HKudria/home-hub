import pytest
from httpx import ASGITransport, AsyncClient
from app.db import init_db
from app.services.medicine_service import MedicineService
from app.web.routes import build_web_router
from app.web.app_factory import create_test_app

@pytest.mark.asyncio
async def test_list_shows_medicine(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    MedicineService(conn).add({"name": "Paracetamol", "quantity": 10})
    app = create_test_app(conn)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/")
    assert r.status_code == 200 and "Paracetamol" in r.text

@pytest.mark.asyncio
async def test_lang_cookie_switch(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    app = create_test_app(conn)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/lang/pl")
        r = await c.get("/")
    assert "Apteczka" in r.text or "apteczka" in r.text.lower()

@pytest.mark.asyncio
async def test_detail(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    mid = MedicineService(conn).add({"name": "A", "quantity": 4})
    app = create_test_app(conn)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get(f"/medicine/{mid}")
    assert r.status_code == 200 and "A" in r.text
