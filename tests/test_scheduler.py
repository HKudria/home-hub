import pytest
from unittest.mock import AsyncMock
from types import SimpleNamespace
from app.config import Settings
from app.db import init_db
from app.services.medicine_service import MedicineService
from app.services.scheduler import run_daily_check, retry_needs_ai

def make_settings():
    return Settings("k", "http://x", "m", "m2", "t", 1, 9, "", ".", 14)

@pytest.mark.asyncio
async def test_daily_check_sends_and_marks(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    MedicineService(conn).add({"name": "A", "expiry_date": "2026-10-06", "quantity": 10})
    bot = AsyncMock()
    n = await run_daily_check(conn, make_settings(), bot, now_date="2026-10-06")
    assert n == 1
    bot.send_message.assert_awaited_once()
    assert conn.execute("SELECT expiry_date FROM medicines").fetchone()["expiry_date"] == "2026-10-06"

@pytest.mark.asyncio
async def test_low_stock_notified_flag_set(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    MedicineService(conn).add({"name": "A", "quantity": 2, "low_stock_threshold": 3})
    bot = AsyncMock()
    await run_daily_check(conn, make_settings(), bot, now_date="2026-10-06")
    assert conn.execute("SELECT low_stock_notified FROM medicines").fetchone()["low_stock_notified"] == 1

@pytest.mark.asyncio
async def test_retry_updates_and_preserves_expiry(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    photo = tmp_path / "p.jpg"; photo.write_bytes(b"img")
    mid = MedicineService(conn).add({"name": "Old", "expiry_date": "2027-01-01"})
    conn.execute("UPDATE medicines SET ai_status='needs_ai_data', photo_path=? WHERE id=?",
                 (str(photo), mid)); conn.commit()
    ext = SimpleNamespace(name="New", expiry_date="2027-03")  # month-precision must be ignored
    fn = AsyncMock(return_value=ext)
    await retry_needs_ai(conn, make_settings(), fn)
    row = conn.execute("SELECT * FROM medicines WHERE id=?", (mid,)).fetchone()
    assert row["name"] == "New" and row["ai_status"] == "ok"
    assert row["expiry_date"] == "2027-01-01"
