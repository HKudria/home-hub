from app.services.alerts import Alert
from app.bot.notify import alert_text, alert_keyboard, callback_to_action

ALERT = Alert("expiry_soon", 3, "Paracetamol", 7)

def test_alert_text():
    s = alert_text("en", ALERT, {"expiry_date": "2026-10-13", "quantity": 10, "unit": "pieces"})
    assert "Paracetamol" in s and "7" in s

def test_all_langs_have_text():
    for lang in ("en", "pl", "ru", "uk"):
        assert "Paracetamol" in alert_text(lang, ALERT, {"expiry_date": "2026-10-13"})

def test_keyboard_expiry():
    kb = alert_keyboard(Alert("expiry_soon", 3, "X", 7))
    datas = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert "discard:3" in datas and "snooze_expiry:3" in datas

def test_keyboard_low_stock():
    kb = alert_keyboard(Alert("low_stock", 3, "X", 2))
    datas = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert datas == ["addlist:3:"]

def test_callback_parse():
    assert callback_to_action("snooze_opened:7") == ("snooze_opened", 7)

def test_callback_addlist_trailing_colon():
    assert callback_to_action("addlist:3:") == ("addlist", 3)

def test_alert_text_accepts_row_like():
    # dict is fine; the defensive dict(med) is for sqlite3.Row — simulate an object without .get
    class RowLike:
        def __getitem__(self, k):
            return {"opened_at": "2026-09-06"}[k]
    s = alert_text("en", Alert("opened_soon", 1, "X", 1), RowLike())
    assert "X" in s
