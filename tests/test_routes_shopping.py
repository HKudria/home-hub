import pytest
from httpx import ASGITransport, AsyncClient
from app.db import init_db
from app.web.app_factory import create_test_app


@pytest.mark.asyncio
async def test_add_items_route(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    app = create_test_app(conn, data_dir=str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/shopping/add", data={"names": "milk, bread"})
    assert r.status_code == 303
    rows = conn.execute("SELECT name FROM shopping_items ORDER BY id").fetchall()
    assert [row["name"] for row in rows] == ["milk", "bread"]


@pytest.mark.asyncio
async def test_check_toggle(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    app = create_test_app(conn, data_dir=str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/shopping/add", data={"names": "milk"})
        assert r.status_code == 303
        item_id = conn.execute(
            "SELECT id FROM shopping_items").fetchone()["id"]
        r = await c.post(f"/shopping/check/{item_id}")
        assert r.status_code == 303
        assert conn.execute(
            "SELECT bought FROM shopping_items WHERE id=?",
            (item_id,)).fetchone()["bought"] == 1
        r = await c.post(f"/shopping/check/{item_id}")
        assert r.status_code == 303
        assert conn.execute(
            "SELECT bought FROM shopping_items WHERE id=?",
            (item_id,)).fetchone()["bought"] == 0


@pytest.mark.asyncio
async def test_check_missing_redirects(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    app = create_test_app(conn, data_dir=str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/shopping/check/999")
    assert r.status_code == 303


@pytest.mark.asyncio
async def test_clear(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    app = create_test_app(conn, data_dir=str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/shopping/add", data={"names": "milk, bread"})
        for row in conn.execute("SELECT id FROM shopping_items").fetchall():
            await c.post(f"/shopping/check/{row['id']}")
        r = await c.post("/shopping/clear")
        assert r.status_code == 303
    assert conn.execute("SELECT COUNT(*) c FROM shopping_items").fetchone()["c"] == 0


@pytest.mark.asyncio
async def test_page_shows_items(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    app = create_test_app(conn, data_dir=str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/shopping/add", data={"names": "paracetamol"})
        r = await c.get("/shopping")
    assert r.status_code == 200
    assert "paracetamol" in r.text
