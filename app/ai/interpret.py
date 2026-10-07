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
    raw = d.get("amount", 1)
    if isinstance(raw, (list, dict)):
        return None
    try:
        amount = float(raw or 1)
    except (ValueError, TypeError):
        return None
    return Intent(action=d["action"], medicine_query=str(d.get("medicine_query", "")).lower(),
                  amount=amount, symptom=str(d.get("symptom", "")))

async def interpret(settings, text: str) -> Intent:
    payload = {"model": settings.zai_text_model,
               "max_tokens": 1024,
               "system": PROMPT,
               "messages": [{"role": "user", "content": text}]}
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{settings.zai_base_url.rstrip('/')}/v1/messages",
                             json=payload,
                             headers={"x-api-key": settings.zai_api_key,
                                      "anthropic-version": "2023-06-01"})
            r.raise_for_status()
            data = r.json()
            content = "".join(block.get("text", "") for block in data.get("content", [])
                              if isinstance(block, dict))
        return parse_intent(content) or Intent("unknown")
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError):
        return Intent("unknown")
