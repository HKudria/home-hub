import json, re
from dataclasses import dataclass
import httpx

PROMPT = (
    "Classify the user's message about their home medicine cabinet. Reply ONLY with JSON: "
    '{"action":"take|opened|query_qty|expiring|symptom|unknown","medicine_query":"<which medicine, lowercase, or empty>","amount":<number, default 1>,"symptom":"<symptom if any, in English>"}\n'
    'Examples: "took 2 ibuprofen" -> take; "открыл сироп" -> opened; "сколько парацетамола?" -> query_qty; '
    '"что скоро истекает?" -> expiring; "болит голова, что есть?" -> symptom; greetings -> unknown.'
)

@dataclass
class Intent:
    action: str
    medicine_query: str = ""
    amount: float = 1
    symptom: str = ""

VALID = {"take", "opened", "query_qty", "expiring", "symptom", "unknown"}

def parse_intent(text: str) -> Intent | None:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if d.get("action") not in VALID:
        return None
    return Intent(action=d["action"], medicine_query=str(d.get("medicine_query", "")).lower(),
                  amount=float(d.get("amount", 1) or 1), symptom=str(d.get("symptom", "")))

async def interpret(settings, text: str) -> Intent:
    payload = {"model": settings.zai_text_model,
               "messages": [{"role": "system", "content": PROMPT},
                            {"role": "user", "content": text}]}
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{settings.zai_base_url}/chat/completions",
                             json=payload, headers={"Authorization": f"Bearer {settings.zai_api_key}"})
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        return Intent("unknown")
    return parse_intent(content) or Intent("unknown")
