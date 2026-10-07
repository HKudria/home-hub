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

@pytest.mark.asyncio
async def test_interpret_fallback(monkeypatch):
    class FakeResp:
        def raise_for_status(self): pass
        def json(self): return {"choices": [{"message": {"content": "???"}}]}
    async def fake_post(self, url, **kw):
        return FakeResp()
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    s = Settings("k", "http://x", "m", "m2", "t", 1, 9, "", ".", 14)
    i = await interpret(s, "???")
    assert i.action == "unknown"
