from app.db import init_db
from app.services.medicine_service import MedicineService
from app.bot.router import match_medicines, symptom_matches, describe_matches, parse_pick_data

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
