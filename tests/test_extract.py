import json, httpx, pytest
from app.config import Settings
from app.ai.client import parse_extraction, extract_medicine

RAW = {
    "name": "Paracetamol 500 mg",
    "active_ingredient": "paracetamol",
    "form": "tablets",
    "dosage_pl": "1 tabletka do 3 razy dziennie",
    "dosage_ru": "1 таблетка до 3 раз в день",
    "dosage_uk": "1 таблетка до 3 разів на день",
    "dosage_en": "1 tablet up to 3x daily",
    "description_pl": "Lek na ból i gorączkę.",
    "description_ru": "Обезболивающее и жаропонижающее.",
    "description_uk": "Знеболювальне та жарознижуюче.",
    "description_en": "Pain and fever relief.",
    "expiry_date": "2027-03",
}

def test_parse_ok():
    e = parse_extraction(json.dumps(RAW))
    assert e.name == "Paracetamol 500 mg"
    assert e.expiry_date == "2027-03"
    assert e.dosage_pl == "1 tabletka do 3 razy dziennie"

def test_parse_wrapped_in_markdown():
    e = parse_extraction("```json\n" + json.dumps(RAW) + "\n```")
    assert e is not None and e.name == "Paracetamol 500 mg"

def test_parse_garbage_returns_none():
    assert parse_extraction("sorry I cannot") is None

def test_parse_missing_name_returns_none():
    e = parse_extraction(json.dumps({"description_en": "x"}))
    assert e is None

def test_parse_multiple_packages():
    e = parse_extraction(json.dumps({"multiple": True, "items": 3}))
    assert e is not None and e.multiple is True

@pytest.mark.asyncio
async def test_extract_medicine_http(monkeypatch):
    async def fake_post(self, url, **kw):
        content = {"choices": [{"message": {"content": json.dumps(RAW)}}]}
        return httpx.Response(200, json=content, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    s = Settings("k", "http://x", "m", "m2", "t", 1, 9, "", ".", 14)
    e = await extract_medicine(s, [b"img"])
    assert e.name == "Paracetamol 500 mg"

@pytest.mark.asyncio
async def test_extract_medicine_http_error(monkeypatch):
    async def fake_post(self, url, **kw):
        raise httpx.ConnectError("boom")
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    s = Settings("k", "http://x", "m", "m2", "t", 1, 9, "", ".", 14)
    assert await extract_medicine(s, [b"img"]) is None
