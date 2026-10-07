import pytest
from app.config import Settings
from app.main import create_app


def test_create_app_smoke(tmp_path):
    s = Settings("k", "http://x", "m", "m2", "", 0, 9, "", str(tmp_path), 14)
    app = create_app(s)
    assert app.state.conn is not None
    assert app.state.services["medicines"] is not None


def test_admin_seeded(tmp_path):
    s = Settings("k", "http://x", "m", "m2", "", 42, 9, "", str(tmp_path), 14)
    app = create_app(s)
    row = app.state.conn.execute("SELECT * FROM allowed_users WHERE telegram_id=42").fetchone()
    assert row is not None and row["role"] == "member"
