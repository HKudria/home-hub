"""Deterministic rule-based intent parsing, tried before the cloud AI.

Pure stdlib. parse_rule_intent returns an Intent (app.ai.interpret) when a
rule matches, or None so the caller can fall back to the cloud interpreter.
Symptom queries, addtask and anything ambiguous return None.

COPY RULE: captured medicine/item text is copied VERBATIM from the original
message — never translated, transliterated, or re-cased.
"""

import re

from app.ai.interpret import Intent

# Longest-first so multi-word verbs win over their prefixes.
TAKE_VERBS = [
    "wziąłem", "wzięłam", "wzięłem", "przyjąłem", "przyjęłam", "brałem",
    "brałam", "took", "take", "had",
    "принял", "приняла", "выпил", "выпила", "попил", "взял", "взяла",
    "узяв", "узяла", "прийняв", "прийняла", "випив", "випила",
]
OPENED_VERBS = [
    "otworzyłem", "otworzyłam", "opened",
    "открыл", "открыла", "відкрив", "відкрила",
]
BOUGHT_VERBS = [
    "bought", "kupiłem", "kupiłam",
    "купил", "купила", "придбав", "придбала",
]
ADDLIST_VERBS = ["add", "dodaj", "додай", "добавь", "добавити"]
QTY_PREFIXES = ["how much", "ile", "сколько", "скільки"]

_SYMPTOM = re.compile(
    r"\b(boli|bole|głowa|glowa|headache|болит|болить|боліть)\b")
_GREETINGS = {"hello", "hi", "hey", "cześć", "dzień dobry", "привет",
              "добрый день", "вітання"}

_TRAIL_PUNCT = re.compile(r"[?.!]+\s*$")
_ITEM_SEP = re.compile(r"\s+и\s+|\s+та\s+|,\s*|\s+i\s+|\s+і\s+")

# Containment-style matches, tried after the specific verbs.
_SHOWLIST_EXACT = {"list", "lista", "список", "список покупок"}
_SHOWLIST_CONTAINS = ("lista zakupów", "список покупок", "shopping list")
_SHOWTASKS = re.compile(
    r"^(?:show|pokaż|покажи)?\s*(?:my\s+)?"
    r"(tasks|zadania|задачи|завдання)[?.!]*$")
_EXPIRING = ("expiring", "ważność", "termin ważności", "истекает",
             "придатність", "кінчається")


def _verb_rule(lower: str, original: str, verbs: list[str], action: str,
               amount_action: bool = False) -> Intent | None:
    for verb in verbs:
        m = re.match(rf"^{verb}\s+(.+)$", lower)
        if not m:
            continue
        rest_l = m.group(1)
        amount = 1
        rest = _TRAIL_PUNCT.sub("", original[m.start(1):]).strip()
        if amount_action:
            am = re.match(r"^(\d+)\s+(.+)$", rest_l)
            if am:
                amount = int(am.group(1))
                rest = original[m.start(1) + am.start(2):
                                m.start(1) + am.end(2)].strip()
        return Intent(action=action, medicine_query=rest, amount=amount)
    return None


def parse_rule_intent(text: str) -> Intent | None:
    if not text or not text.strip():
        return None
    original = text.strip()
    lower = original.lower()

    # Never claim these: they belong to the cloud AI (or no one).
    if _SYMPTOM.search(lower):
        return None
    if _TRAIL_PUNCT.sub("", lower) in _GREETINGS:
        return None

    # Specific verbs first.
    hit = (_verb_rule(lower, original, TAKE_VERBS, "take", amount_action=True)
           or _verb_rule(lower, original, OPENED_VERBS, "opened")
           or _verb_rule(lower, original, BOUGHT_VERBS, "bought"))
    if hit:
        return hit

    m = re.match(rf"^({'|'.join(ADDLIST_VERBS)})\s+(.+)$", lower)
    if m:
        # "add task ..." / "додай задачу ..." is addtask — cloud AI only.
        if re.match(r"^(task|zadanie|задач\w*|завдан\w*)\b", m.group(2)):
            return None
        rest = original[m.end(1):]
        items = [it.strip() for it in _ITEM_SEP.split(rest) if it.strip()]
        if items:
            return Intent(action="addlist", items=items)

    m = re.match(rf"^({'|'.join(QTY_PREFIXES)})\s+(.+)$", lower)
    if m:
        rest = original[m.start(2):].rstrip("?").strip()
        rest = re.sub(r"^(of|jest)\s+", "", rest, flags=re.IGNORECASE)
        if rest:
            return Intent(action="query_qty", medicine_query=rest)

    # Containment matches.
    bare = _TRAIL_PUNCT.sub("", lower).strip()
    if bare in _SHOWLIST_EXACT or any(s in lower for s in _SHOWLIST_CONTAINS):
        return Intent(action="showlist")

    if _SHOWTASKS.match(lower):
        return Intent(action="showtasks")

    if any(s in lower for s in _EXPIRING):
        return Intent(action="expiring")

    return None
