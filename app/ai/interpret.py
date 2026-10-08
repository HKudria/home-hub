import json, re
from dataclasses import dataclass, field
import httpx

PROMPT = (
    "Classify the user's message about their home medicine cabinet or family tasks. Reply ONLY with JSON: "
    '{"action":"take|opened|query_qty|expiring|symptom|addlist|bought|showlist|addtask|donetask|showtasks|unknown",'
    '"medicine_query":"<which medicine or task title, lowercase, or empty>","amount":<number, default 1>,'
    '"symptom":"<symptom if any, in English>","items":["<shopping item>", ...],'
    '"task_title":"<task title, or empty>","due_date":"<YYYY-MM-DD or null>","assignee":"<person name, or empty>"}\n'
    'Examples: "took 2 ibuprofen" -> take; "открыл сироп" -> opened; "сколько парацетамола?" -> query_qty; '
    '"что скоро истекает?" -> expiring; "болит голова, что есть?" -> symptom; '
    '"add milk and bread" -> addlist with items ["milk","bread"]; "bought milk" -> bought with medicine_query "milk"; '
    '"show shopping list" / "что в списке?" -> showlist; '
    '"add task pay bills on friday" -> addtask with task_title "pay bills" and due_date the ISO date of the coming friday (null if no date); '
    '"напомни Анне полить цветы завтра" -> addtask with task_title "полить цветы", assignee "Анна" and due_date of tomorrow; '
    '"task pay bills is done" -> donetask with medicine_query "pay bills"; '
    '"show tasks" / "какие задачи?" -> showtasks; greetings -> unknown.'
)

_FULL_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

@dataclass
class Intent:
    action: str
    medicine_query: str = ""
    amount: float = 1
    symptom: str = ""
    items: list[str] = field(default_factory=list)
    task_title: str = ""
    due_date: str | None = None
    assignee: str = ""

VALID = {"take", "opened", "query_qty", "expiring", "symptom",
         "addlist", "bought", "showlist", "addtask", "donetask", "showtasks",
         "unknown"}

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
    items: list[str] = []
    raw_items = d.get("items")
    try:
        if isinstance(raw_items, list):
            for it in raw_items:
                if isinstance(it, str) and it.strip():
                    items.append(it.strip())
    except (TypeError, ValueError):
        items = []
    task_title, assignee, due_date = "", "", None
    try:
        raw_title = d.get("task_title")
        if isinstance(raw_title, str):
            task_title = raw_title.strip()
        raw_assignee = d.get("assignee")
        if isinstance(raw_assignee, str):
            assignee = raw_assignee.strip()
        raw_due = d.get("due_date")
        if isinstance(raw_due, str):
            candidate = raw_due.strip()
            if _FULL_DATE.fullmatch(candidate):
                due_date = candidate
    except (TypeError, ValueError):
        task_title, assignee, due_date = "", "", None
    return Intent(action=d["action"], medicine_query=str(d.get("medicine_query", "")).lower(),
                  amount=amount, symptom=str(d.get("symptom", "")), items=items,
                  task_title=task_title, due_date=due_date, assignee=assignee)

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
