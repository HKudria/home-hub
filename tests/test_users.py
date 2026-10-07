from app.db import init_db
from app.bot.users import is_allowed, approve, decline

def conn_with():
    return init_db(":memory:")

def test_pending_not_allowed():
    c = conn_with()
    c.execute("INSERT INTO allowed_users (telegram_id, role) VALUES (5, 'pending')")
    assert not is_allowed(c, 5)

def test_approve():
    c = conn_with()
    c.execute("INSERT INTO allowed_users (telegram_id, role) VALUES (5, 'pending')")
    approve(c, 5)
    assert is_allowed(c, 5)
    decline(c, 5)
    assert not is_allowed(c, 5)
