from app.db import init_db
from app.services.medicine_service import MedicineService
from app.services.shopping_service import ShoppingService
from app.bot.router import (match_medicines, symptom_matches, describe_matches,
                            parse_pick_data, format_list_contents,
                            format_open_tasks)

def make(tmp_path):
    conn = init_db(str(tmp_path / "t.db"))
    svc = MedicineService(conn)
    a = svc.add({"name": "Paracetamol 500", "quantity": 10,
                 "description_en": "Pain and fever relief.",
                 "description_pl": "Lek na ból i gorączkę."})
    b = svc.add({"name": "Paracetamol kids", "quantity": 5})
    return conn, svc, a, b

def test_match_one(tmp_path):
    conn, svc, a, b = make(tmp_path)
    assert [r["id"] for r in match_medicines(conn, "500")] == [a]

def test_match_two_ambiguous(tmp_path):
    conn, svc, a, b = make(tmp_path)
    assert len(match_medicines(conn, "paracetamol")) == 2

def test_symptom_pl(tmp_path):
    conn, svc, a, b = make(tmp_path)
    assert [r["id"] for r in symptom_matches(conn, "headache")] == [a]

def test_describe(tmp_path):
    conn, svc, a, b = make(tmp_path)
    rows = match_medicines(conn, "paracetamol")
    s = describe_matches(rows, "en")
    assert "Paracetamol 500" in s and "10 pieces" in s

def test_parse_pick_data():
    assert parse_pick_data("pick:12:1") == (12, 1.0)
    assert parse_pick_data("pick:7:2.5") == (7, 2.5)
    assert parse_pick_data("pick:9") == (9, 1.0)

def test_format_list_contents(tmp_path):
    conn = init_db(str(tmp_path / "shop.db"))
    svc = ShoppingService(conn)
    svc.add_items(["milk", "bread"], "Tester")
    rows = svc.list_unbought()
    assert format_list_contents(rows, "en") == "Shopping list:\n• milk\n• bread"

def test_format_list_contents_empty():
    assert format_list_contents([], "en") == ""

def test_format_open_tasks_overdue():
    rows = [{"title": "pay bills", "due_date": "2026-10-01",
             "assignee_name": "Anna"}]
    assert format_open_tasks(rows, "en", "2026-10-08") == \
        "Open tasks:\n• OVERDUE pay bills — due 2026-10-01 → Anna"

def test_format_open_tasks_due_today():
    rows = [{"title": "water plants", "due_date": "2026-10-08",
             "assignee_name": "Anna"}]
    assert format_open_tasks(rows, "en", "2026-10-08") == \
        "Open tasks:\n• water plants — due 2026-10-08 → Anna"

def test_format_open_tasks_no_due():
    rows = [{"title": "tidy up", "due_date": None, "assignee_name": "Anna"}]
    assert format_open_tasks(rows, "en", "2026-10-08") == \
        "Open tasks:\n• tidy up → Anna"

def test_format_open_tasks_no_assignee():
    rows = [{"title": "buy salt", "due_date": "2026-10-08", "assignee_name": None}]
    assert format_open_tasks(rows, "en", "2026-10-08") == \
        "Open tasks:\n• buy salt — due 2026-10-08"

def test_format_open_tasks_empty():
    assert format_open_tasks([], "en", "2026-10-08") == ""
