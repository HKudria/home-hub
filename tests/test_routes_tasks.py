import pytest
from httpx import ASGITransport, AsyncClient
from app.db import init_db
from app.web.app_factory import create_test_app


@pytest.mark.asyncio
async def test_add_task_route(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    app = create_test_app(conn, data_dir=str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/tasks/add", data={"title": "pay bills"})
    assert r.status_code == 303
    row = conn.execute(
        "SELECT title, created_by FROM tasks").fetchone()
    assert row["title"] == "pay bills"
    assert row["created_by"] == "web"


@pytest.mark.asyncio
async def test_add_requires_title(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    app = create_test_app(conn, data_dir=str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/tasks/add", data={"title": "   "})
    assert r.status_code == 400
    assert conn.execute("SELECT COUNT(*) c FROM tasks").fetchone()["c"] == 0


@pytest.mark.asyncio
async def test_complete_toggle(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    app = create_test_app(conn, data_dir=str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/tasks/add", data={"title": "water plants"})
        task_id = conn.execute("SELECT id FROM tasks").fetchone()["id"]
        r = await c.post(f"/tasks/complete/{task_id}")
        assert r.status_code == 303
        row = conn.execute(
            "SELECT done, done_by FROM tasks WHERE id=?", (task_id,)).fetchone()
        assert row["done"] == 1
        assert row["done_by"] == "web"
        r = await c.post(f"/tasks/complete/{task_id}")
        assert r.status_code == 303
        row = conn.execute(
            "SELECT done FROM tasks WHERE id=?", (task_id,)).fetchone()
        assert row["done"] == 0


@pytest.mark.asyncio
async def test_page_shows_task(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    app = create_test_app(conn, data_dir=str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/tasks/add",
                     data={"title": "pay bills", "due_date": "2020-01-01"})
        r = await c.get("/tasks")
    assert r.status_code == 200
    assert "pay bills" in r.text
    assert "OVERDUE" in r.text
