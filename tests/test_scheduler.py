import pytest
from unittest.mock import AsyncMock
from app.config import Settings
from app.db import init_db
from app.services.medicine_service import MedicineService
from app.services.scheduler import run_daily_check

def make_settings():
    return Settings("k", "http://x", "m", "m2", "t", 1, 9, "", ".", 14)

@pytest.mark.asyncio
async def test_daily_check_sends_and_marks(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    MedicineService(conn).add({"name": "A", "expiry_date": "2026-10-06"})
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
