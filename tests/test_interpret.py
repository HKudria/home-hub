import json, httpx, pytest
from app.config import Settings
from app.ai.interpret import parse_intent, interpret

def test_take():
    i = parse_intent('{"action":"take","medicine_query":"paracetamol","amount":1,"symptom":""}')
    assert (i.action, i.medicine_query, i.amount) == ("take", "paracetamol", 1)

def test_symptom():
    i = parse_intent('{"action":"symptom","medicine_query":"","amount":1,"symptom":"headache"}')
    assert i.action == "symptom" and i.symptom == "headache"

def test_garbage():
    assert parse_intent("hello") is None

def test_parse_intent_bad_amount_returns_none():
    assert parse_intent('{"action":"take","medicine_query":"x","amount":"many"}') is None
    assert parse_intent('{"action":"take","medicine_query":"x","amount":[]}') is None

def test_addlist_items():
    i = parse_intent('{"action":"addlist","medicine_query":"","amount":1,'
                     '"symptom":"","items":["milk"," bread"]}')
    assert i.action == "addlist"
    assert i.items == ["milk", "bread"]

def test_bought_action():
    i = parse_intent('{"action":"bought","medicine_query":"milk","amount":1,"symptom":""}')
    assert i.action == "bought"
    assert i.medicine_query == "milk"

def test_showlist_action():
    i = parse_intent('{"action":"showlist","medicine_query":"","amount":1,"symptom":""}')
    assert i.action == "showlist"

def test_malformed_items_become_empty():
    i = parse_intent('{"action":"addlist","items":"x"}')
    assert i is not None and i.items == []
    i = parse_intent('{"action":"addlist","items":{}}')
    assert i is not None and i.items == []
    i = parse_intent('{"action":"addlist"}')
    assert i is not None and i.items == []

def test_addtask_full():
    i = parse_intent('{"action":"addtask","medicine_query":"","amount":1,"symptom":"",'
                     '"items":[],"task_title":" pay bills ","due_date":"2026-10-10","assignee":" Anna "}')
    assert i.action == "addtask"
    assert i.task_title == "pay bills"
    assert i.due_date == "2026-10-10"
    assert i.assignee == "Anna"

def test_addtask_no_due():
    i = parse_intent('{"action":"addtask","task_title":"tidy up","due_date":null,"assignee":""}')
    assert i.task_title == "tidy up"
    assert i.due_date is None
    assert i.assignee == ""

def test_donetask_action():
    i = parse_intent('{"action":"donetask","medicine_query":"pay bills"}')
    assert i.action == "donetask"
    assert i.medicine_query == "pay bills"

def test_items_preserve_original_language():
    i = parse_intent('{"action":"addlist","medicine_query":"","amount":1,"symptom":"","items":["хліб","молоко"]}')
    assert i.items == ["хліб", "молоко"]

def test_task_title_preserves_original_language():
    i = parse_intent('{"action":"addtask","task_title":"полити квіти","due_date":null,"assignee":"Анна","medicine_query":"","amount":1,"symptom":""}')
    assert i.task_title == "полити квіти"

def test_showtasks_action():
    i = parse_intent('{"action":"showtasks"}')
    assert i.action == "showtasks"

def test_bad_due_date_becomes_none():
    i = parse_intent('{"action":"addtask","task_title":"x","due_date":"friday"}')
    assert i is not None and i.due_date is None
    i = parse_intent('{"action":"addtask","task_title":"x","due_date":123}')
    assert i is not None and i.due_date is None
    i = parse_intent('{"action":"addtask","task_title":"x","due_date":"2026-13"}')
    assert i is not None and i.due_date is None

def test_malformed_task_fields_default():
    i = parse_intent('{"action":"addtask","task_title":5,"assignee":[]}')
    assert i is not None and i.task_title == "" and i.assignee == "" and i.due_date is None

@pytest.mark.asyncio
async def test_interpret_fallback(monkeypatch):
    class FakeResp:
        def raise_for_status(self): pass
        def json(self): return {"content": [{"type": "text", "text": "???"}]}
    async def fake_post(self, url, **kw):
        return FakeResp()
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    s = Settings("k", "http://x", "m", "m2", "t", 1, 9, "", ".", 14)
    i = await interpret(s, "???")
    assert i.action == "unknown"
