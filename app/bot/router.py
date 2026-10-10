"""Telegram router: commands, free-text intent dispatch, callback handling.

`build_router(conn, settings, services)` wires every handler against the
shared sqlite connection and the services dict
({"medicines": MedicineService, "shopping": ShoppingService | None}).
"""

import datetime
import difflib
import json
import re
import sqlite3

import httpx
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, KeyboardButton, Message, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.ai.interpret import Intent, interpret
from app.bot.notify import callback_to_action
from app.bot.rule_agent import parse_rule_intent
from app.bot.users import approve, decline, is_admin, is_allowed, request_approval
from app.config import Settings
from app.i18n import DEFAULT_LANG, t, unit_label
from app.services.medicine_service import MedicineService
from app.services.shopping_service import ShoppingService
from app.services.task_service import TaskService

LANG_CODES = ("en", "pl", "ru", "uk")

# Pending pick resolutions: {(chat_id, user_id): action}. The pick:<id>:<amount>
# callback pops it; stale entries are simply overwritten by newer ones.
PENDING: dict[tuple[int, int], str] = {}

# The plain LIKE search cannot know that "headache" relates to "pain" when the
# description is written in another wording, so a small built-in map extends
# symptom_matches with related terms (additive only — direct matches unchanged).
SYMPTOM_SYNONYMS: dict[str, list[str]] = {
    "headache": ["pain", "ból", "головная боль", "головний біль"],
    "fever": ["gorączka", "temperatura", "жар", "лихоманка"],
    "cough": ["kaszel", "кашель", "кашлю"],
    "cold": ["przeziębienie", "простуда", "застуда"],
    "pain": ["ból", "боль", "біль"],
}


# ---------------------------------------------------------------- helpers

def match_medicines(conn: sqlite3.Connection, query: str) -> list:
    q = f"%{query.strip().lower()}%"
    return conn.execute(
        "SELECT * FROM medicines WHERE lower(name) LIKE ? OR lower(active_ingredient) LIKE ? "
        "ORDER BY id", (q, q)).fetchall()


def fuzzy_matches(conn: sqlite3.Connection, query: str, table: str = "medicines",
                  limit: int = 4) -> list:
    """Fuzzy-find rows when the exact LIKE search came up empty.

    Token-level difflib matching: every query token (>=3 chars) must reach
    a 0.75 similarity ratio against some token of the row's text (this
    accepts inflection/typo pairs like plaster/plastry or odcsiki/odciski).
    Rows are ranked by the share of query tokens matched, then by id;
    only rows scoring above 0 are returned. `table` selects the searched
    text: "medicines" (name), "shopping_items" (name) or "tasks" (title).
    """
    text_col = "title" if table == "tasks" else "name"
    q_tokens = [tok for tok in query.lower().split() if len(tok) >= 3]
    if not q_tokens:
        return []
    scored = []
    for r in conn.execute(f"SELECT * FROM {table}").fetchall():
        n_tokens = r[text_col].lower().split()
        matched = 0
        for qt in q_tokens:
            best = max((difflib.SequenceMatcher(None, qt, nt).ratio()
                        for nt in n_tokens), default=0.0)
            if best >= 0.75:
                matched += 1
        score = matched / len(q_tokens)
        if score > 0:
            scored.append((score, r["id"], r))
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [r for _, _, r in scored[:limit]]


def _word_tokens(text: str) -> list:
    """Lowercase word tokens (letters only, len >= 4) of `text`."""
    return [w for w in re.findall(r"[^\W\d_]+", text.lower()) if len(w) >= 4]


def symptom_matches(conn: sqlite3.Connection, terms: list, limit: int = 4) -> list:
    """Weighted tokenized symptom search over name + ingredient + descriptions.

    `terms` is a list of symptom phrases (e.g. from the AI translator, so
    possibly PL/RU/). Every phrase — plus its SYMPTOM_SYNONYMS expansions,
    each kept as a separate token group so a synonym in another language
    does not dilute the score — is split into lowercase word tokens
    (len >= 4). A token T scores against a medicine when some word W of its
    combined text satisfies W.startswith(T) or T.startswith(W) (so "gardła"
    matches "gardła", "stan" matches "stanach"). Token weight is its length.

    A medicine is included only when, for at least one token group, the
    matched weight reaches 60% of that group's total weight AND at least one
    matched token is "specific": len >= 5, or an exact whole-word match
    (so "gardła"/"zapalny" qualify; a lone 4-char generic like "stan" or an
    exact "pain" synonym hit does not block inclusion). Rows are ranked by
    best ratio, then total matched weight, then id, and limited to `limit`.
    The old single-string signature is still accepted for convenience.
    """
    if isinstance(terms, str):
        terms = [terms]
    groups: list[list[str]] = []
    for term in terms:
        if not term:
            continue
        groups.append(_word_tokens(term))
        for syn in SYMPTOM_SYNONYMS.get(term.lower().strip(), []):
            groups.append(_word_tokens(syn))
    groups = [g for g in groups if g]
    if not groups:
        return []
    weights = [sum(len(t) for t in g) for g in groups]
    scored = []
    for r in conn.execute("SELECT * FROM medicines").fetchall():
        text = " ".join(filter(None, (
            r["name"], r["active_ingredient"],
            r["description_pl"], r["description_ru"],
            r["description_uk"], r["description_en"]))).lower()
        words = _word_tokens(text)
        best_ratio = 0.0
        best_matched, groups_covered, specific = 0, 0, False
        for g, g_weight in zip(groups, weights):
            matched = 0
            for tk in g:
                hit = next((w for w in words
                            if w.startswith(tk) or tk.startswith(w)), None)
                if hit is not None:
                    matched += len(tk)
                    if len(tk) >= 5 or hit == tk:
                        specific = True
            ratio = min(1.0, matched / g_weight)
            if ratio >= 0.6:
                groups_covered += 1
            # Rank by the BEST single term group (capped at 1.0), not the sum
            # over groups: summing favours medicines whose descriptions echo
            # several language variants over medicines that match one language
            # perfectly.
            if ratio > best_ratio or (
                    ratio == best_ratio and matched > best_matched):
                best_ratio = ratio
                best_matched = matched
        if best_ratio >= 0.6 and specific:
            scored.append((groups_covered, best_ratio, best_matched, r["id"], r))
    scored.sort(key=lambda s: (-s[0], -s[1], -s[2], s[3]))
    return [r for _, _, _, _, r in scored[:limit]]


def describe_matches(rows, lang: str) -> str:
    lines = []
    for r in rows:
        lines.append(f"• {r['name']} — {int(r['quantity'])} {unit_label(lang, r['unit'])}")
    return "\n".join(lines)


def describe_matches_enhanced(rows, lang: str) -> str:
    """Like describe_matches, but appends a warning mark to medicines that
    are expired or past their discard-by date."""
    today = datetime.date.today().isoformat()
    lines = []
    for r in rows:
        warn = False
        if r["expiry_date"] and r["expiry_date"] < today:
            warn = True
        elif r["opened_at"] and r["discard_after_days"]:
            try:
                discard_by = (datetime.date.fromisoformat(r["opened_at"])
                              + datetime.timedelta(days=int(r["discard_after_days"]))).isoformat()
            except (ValueError, TypeError):
                discard_by = None
            if discard_by and discard_by < today:
                warn = True
        mark = " ⚠️" if warn else ""
        lines.append(f"• {r['name']} — {int(r['quantity'])} {unit_label(lang, r['unit'])}{mark}")
    return "\n".join(lines)


def parse_pick_data(data: str):
    """Return (medicine_id, amount) from 'pick:<id>:<amount>'."""
    parts = data.split(":")
    return int(parts[1]), float(parts[2]) if len(parts) > 2 and parts[2] else 1.0


def format_list_contents(rows, lang: str) -> str:
    """Render unbought shopping-list rows as "Shopping list:" + bullet lines.

    Returns "" for an empty list so the caller can send list_empty instead.
    """
    if not rows:
        return ""
    lines = [t(lang, "list_contents")]
    lines += [f"• {r['name']}" for r in rows]
    return "\n".join(lines)


def format_open_tasks(rows, lang: str, today: str) -> str:
    """Render open task rows as "Open tasks:" + bullet lines.

    A due date before `today` gets the OVERDUE prefix; a due date of today
    (or later) is shown after an em dash. The assignee (if any) is appended
    as " → name". Returns "" for an empty list so the caller can send
    task_empty instead.
    """
    if not rows:
        return ""
    lines = [t(lang, "task_list")]
    for r in rows:
        due = r["due_date"]
        who = t(lang, "task_assigned_note", who=r["assignee_name"]) \
            if r["assignee_name"] else ""
        mark = f"{t(lang, 'task_overdue')} " if due and due < today else ""
        tail = f" —{t(lang, 'task_due', date=due)}" if due else ""
        lines.append(f"• {mark}{r['title']}{tail}{who}")
    return "\n".join(lines)


def get_user_lang(conn: sqlite3.Connection, tg_id: int) -> str:
    row = conn.execute("SELECT lang FROM allowed_users WHERE telegram_id=?", (tg_id,)).fetchone()
    if row and row["lang"] in LANG_CODES:
        return row["lang"]
    return DEFAULT_LANG


def actor_name(user) -> str:
    if user is None:
        return ""
    return user.full_name or (f"@{user.username}" if user.username else "")


# Template buttons: kb_* i18n key -> intent they short-circuit to.
TEMPLATE_BUTTONS: tuple[tuple[str, str], ...] = (
    ("kb_shopping", "showlist"),
    ("kb_tasks", "showtasks"),
    ("kb_expiring", "expiring"),
    ("kb_language", "language"),
)


def match_template(text: str, lang: str) -> str | None:
    """Return 'showlist' | 'showtasks' | 'expiring' | 'language' when text equals
    the localized template button text for lang, else None."""
    stripped = text.strip()
    for key, action in TEMPLATE_BUTTONS:
        if stripped == t(lang, key):
            return action
    return None


def main_keyboard(lang: str) -> ReplyKeyboardMarkup:
    """Persistent reply keyboard with the common-request templates."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "kb_shopping")),
             KeyboardButton(text=t(lang, "kb_tasks"))],
            [KeyboardButton(text=t(lang, "kb_expiring")),
             KeyboardButton(text=t(lang, "kb_language"))],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


async def symptom_terms(settings: Settings, symptom: str) -> list:
    """Translate a symptom to PL/RU/UK via one z.ai text-model call.

    Returns [symptom] itself on any failure, so callers can union safely.
    """
    if not symptom:
        return []
    payload = {
        "model": settings.zai_text_model,
        "max_tokens": 1024,
        "system": ('Translate this symptom to Polish, Russian, Ukrainian. '
                   'Reply ONLY with JSON: {"pl":"...","ru":"...","uk":"..."}'),
        "messages": [{"role": "user", "content": "Symptom: " + symptom}],
    }
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                f"{settings.zai_base_url.rstrip('/')}/v1/messages",
                json=payload,
                headers={"x-api-key": settings.zai_api_key,
                         "anthropic-version": "2023-06-01"},
            )
            r.raise_for_status()
            data = r.json()
            content = "".join(block.get("text", "") for block in data.get("content", [])
                              if isinstance(block, dict))
        m = re.search(r"\{.*\}", content, re.DOTALL)
        if not m:
            return [symptom]
        d = json.loads(m.group(0))
        terms = [str(d[k]).strip() for k in ("pl", "ru", "uk") if d.get(k)]
        return terms or [symptom]
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError):
        return [symptom]


# ---------------------------------------------------------------- builder

def build_router(conn: sqlite3.Connection, settings: Settings,
                 services: dict) -> Router:
    router = Router(name="bot")
    svc: MedicineService = services["medicines"]

    async def do_action(message: Message, tg_id: int, actor: str, action: str,
                        med_id: int, amount: float):
        lang = get_user_lang(conn, tg_id)
        kb = main_keyboard(lang)
        row = svc.get(med_id)
        if row is None:
            await message.reply(t(lang, "no_match"), reply_markup=kb)
            return
        if action == "take":
            row = svc.take_dose(med_id, amount, actor)
            if row is None:
                await message.reply(t(lang, "no_match"), reply_markup=kb)
                return
            if row["quantity"] <= row["low_stock_threshold"]:
                # Only mark notified when the admin took the dose themselves;
                # a family member emptying the box must still alert the admin
                # via the daily check.
                if tg_id == settings.admin_telegram_id:
                    conn.execute("UPDATE medicines SET low_stock_notified=1 WHERE id=?",
                                 (med_id,))
                    conn.commit()
            if row["quantity"] == 0:
                await message.reply(t(lang, "last_dose", name=row["name"]),
                                    reply_markup=kb)
            else:
                await message.reply(t(lang, "took", name=row["name"],
                                      qty=int(row["quantity"]),
                                      unit=unit_label(lang, row["unit"])),
                                    reply_markup=kb)
        elif action == "opened":
            today = datetime.date.today().isoformat()
            svc.mark_opened(med_id, today, actor)
            await message.reply(t(lang, "opened_on", name=row["name"], opened=today),
                                reply_markup=kb)
        elif action == "query_qty":
            await message.reply(t(lang, "took", name=row["name"],
                                  qty=int(row["quantity"]),
                                  unit=unit_label(lang, row["unit"])),
                                reply_markup=kb)
        elif action == "bought":
            svc_shop = services.get("shopping") or ShoppingService(conn)
            item = svc_shop.check_off(str(med_id), actor)
            if item is None:
                await message.reply(t(lang, "no_match"), reply_markup=kb)
            else:
                await message.reply(t(lang, "list_bought", name=item["name"]),
                                    reply_markup=kb)
        elif action == "donetask":
            svc_tasks = services.get("tasks") or TaskService(conn)
            task = svc_tasks.complete(str(med_id), actor)
            if task is None:
                await message.reply(t(lang, "no_match"), reply_markup=kb)
            else:
                await message.reply(t(lang, "task_done", title=task["title"]),
                                    reply_markup=kb)

    async def reply_pick_buttons(message: Message, rows, amount: float,
                                 key: str = "which_one", label_col: str = "name"):
        kb = InlineKeyboardBuilder()
        for r in rows:
            kb.button(text=r[label_col], callback_data=f"pick:{r['id']}:{int(amount)}")
        await message.reply(t(get_user_lang(conn, message.from_user.id), key),
                            reply_markup=kb.as_markup())

    async def send_expiring(message: Message, lang: str):
        """Shared body of the 'expiring' intent and the expiring template."""
        today = datetime.date.today()
        horizon = today + datetime.timedelta(days=7)
        soon = []
        for r in svc.list_all():
            if not r["expiry_date"]:
                continue
            try:
                exp = datetime.date.fromisoformat(r["expiry_date"])
            except (ValueError, TypeError):
                continue
            if today <= exp <= horizon:
                soon.append(r)
        if not soon:
            await message.reply(t(lang, "symptom_none"),
                                reply_markup=main_keyboard(lang))
        else:
            lines = [t(lang, "expiring_soon_list")]
            lines += [f"• {r['name']} — {r['expiry_date']}" for r in soon]
            await message.reply("\n".join(lines),
                                reply_markup=main_keyboard(lang))

    @router.message(Command("start"))
    async def cmd_start(message: Message, bot: Bot):
        tg_id = message.from_user.id
        lang = get_user_lang(conn, tg_id)
        if is_admin(settings, tg_id) or is_allowed(conn, tg_id):
            await message.reply(t(lang, "approved"),
                                reply_markup=main_keyboard(lang))
        else:
            await request_approval(conn, settings, bot, tg_id, actor_name(message.from_user))
            await message.reply(t(lang, "ask_admin"))

    @router.message(Command("help"))
    async def cmd_help(message: Message, bot: Bot):
        tg_id = message.from_user.id
        if not (is_admin(settings, tg_id) or is_allowed(conn, tg_id)):
            # Same gate as free text: unapproved users get the approval flow.
            await request_approval(conn, settings, bot, tg_id,
                                   actor_name(message.from_user))
            await message.reply(t(DEFAULT_LANG, "ask_admin"))
            return
        lang = get_user_lang(conn, tg_id)
        await message.reply(t(lang, "help_text"))

    @router.message(Command("lang"))
    async def cmd_lang(message: Message):
        parts = (message.text or "").split()
        if len(parts) < 2:
            return
        code = parts[1].strip().lower()
        if code not in LANG_CODES:
            return  # invalid: silently ignore
        conn.execute("UPDATE allowed_users SET lang=? WHERE telegram_id=?",
                     (code, message.from_user.id))
        conn.commit()
        await message.reply(t(code, "language"))

    @router.message(F.text)
    async def free_text(message: Message, bot: Bot):
        tg_id = message.from_user.id
        if not (is_admin(settings, tg_id) or is_allowed(conn, tg_id)):
            # Unapproved user: start (or re-show) the approval flow instead
            # of silently ignoring them. request_approval is idempotent.
            await request_approval(conn, settings, bot, tg_id,
                                   actor_name(message.from_user))
            await message.reply(t(DEFAULT_LANG, "ask_admin"))
            return
        lang = get_user_lang(conn, tg_id)
        text = message.text or ""

        # Template button presses short-circuit before the AI interpreter
        # (instant and free), still behind the approval gate above.
        tpl = match_template(text, lang)
        if tpl == "showlist":
            svc_shop = services.get("shopping") or ShoppingService(conn)
            rows = svc_shop.list_unbought()
            body = format_list_contents(rows, lang)
            await message.reply(body if body else t(lang, "list_empty"),
                                reply_markup=main_keyboard(lang))
            return
        if tpl == "showtasks":
            svc_tasks = services.get("tasks") or TaskService(conn)
            rows = svc_tasks.list_open()
            body = format_open_tasks(rows, lang, datetime.date.today().isoformat())
            await message.reply(body if body else t(lang, "task_empty"),
                                reply_markup=main_keyboard(lang))
            return
        if tpl == "expiring":
            await send_expiring(message, lang)
            return
        if tpl == "language":
            kb = InlineKeyboardBuilder()
            for code in LANG_CODES:
                kb.button(text=code.upper(), callback_data=f"setlang:{code}")
            await message.reply(t(lang, "language"), reply_markup=kb.as_markup())
            return

        # Deterministic rules first (free, instant); cloud AI as fallback.
        intent = parse_rule_intent(text)
        if intent is None:
            intent = await interpret(settings, text)

        if intent.action in ("take", "opened", "query_qty"):
            query = intent.medicine_query or text.strip()
            rows = match_medicines(conn, query)
            amount = intent.amount if intent.action == "take" else 1
            if not rows:
                # No exact match: offer fuzzy "did you mean" candidates.
                candidates = fuzzy_matches(conn, query)
                if candidates:
                    PENDING[(message.chat.id, tg_id)] = intent.action
                    await reply_pick_buttons(message, candidates, amount,
                                             key="maybe")
                else:
                    await message.reply(t(lang, "no_match"),
                                        reply_markup=main_keyboard(lang))
            elif len(rows) > 1:
                PENDING[(message.chat.id, tg_id)] = intent.action
                await reply_pick_buttons(message, rows, amount)
            else:
                await do_action(message, tg_id, actor_name(message.from_user),
                                intent.action, rows[0]["id"], amount)

        elif intent.action == "expiring":
            await send_expiring(message, lang)

        elif intent.action == "symptom":
            symptom = intent.symptom or text.strip()
            terms = [symptom]
            try:
                terms += await symptom_terms(settings, symptom)
            except Exception:
                pass
            rows = symptom_matches(conn, [term for term in terms if term])
            if not rows:
                await message.reply(t(lang, "symptom_none"),
                                    reply_markup=main_keyboard(lang))
            else:
                await message.reply(t(lang, "symptom_found") + "\n"
                                    + describe_matches_enhanced(rows, lang),
                                    reply_markup=main_keyboard(lang))

        elif intent.action == "addlist":
            svc_shop = services.get("shopping") or ShoppingService(conn)
            added = svc_shop.add_items(intent.items, actor_name(message.from_user))
            if added:
                await message.reply(t(lang, "list_added", items=", ".join(added)),
                                    reply_markup=main_keyboard(lang))
            else:
                await message.reply(t(lang, "no_match"),
                                    reply_markup=main_keyboard(lang))

        elif intent.action == "bought":
            svc_shop = services.get("shopping") or ShoppingService(conn)
            row = svc_shop.check_off(intent.medicine_query, actor_name(message.from_user))
            if row:
                await message.reply(t(lang, "list_bought", name=row["name"]),
                                    reply_markup=main_keyboard(lang))
            else:
                # No exact match: offer fuzzy candidates (unbought only).
                candidates = [r for r in fuzzy_matches(
                    conn, intent.medicine_query or text.strip(),
                    table="shopping_items") if not r["bought"]]
                if candidates:
                    PENDING[(message.chat.id, tg_id)] = "bought"
                    await reply_pick_buttons(message, candidates, 1, key="maybe")
                else:
                    await message.reply(t(lang, "no_match"),
                                        reply_markup=main_keyboard(lang))

        elif intent.action == "showlist":
            svc_shop = services.get("shopping") or ShoppingService(conn)
            rows = svc_shop.list_unbought()
            body = format_list_contents(rows, lang)
            if body:
                await message.reply(body, reply_markup=main_keyboard(lang))
            else:
                await message.reply(t(lang, "list_empty"),
                                    reply_markup=main_keyboard(lang))

        elif intent.action == "addtask":
            svc_tasks = services.get("tasks") or TaskService(conn)
            actor = actor_name(message.from_user)
            if not intent.task_title:
                await message.reply(t(lang, "no_match"),
                                    reply_markup=main_keyboard(lang))
                return
            assignee_id = None
            assignee_name = None
            if intent.assignee:
                # Python-side case-insensitive substring match so Unicode
                # case folding (e.g. Polish/Ukrainian names) behaves.
                needle = intent.assignee.lower()
                members = conn.execute(
                    "SELECT telegram_id, name FROM allowed_users "
                    "WHERE role='member' AND name != ''").fetchall()
                matches = [m for m in members if needle in m["name"].lower()]
                if len(matches) == 1:
                    assignee_id = matches[0]["telegram_id"]
                    assignee_name = matches[0]["name"]
            row = svc_tasks.add_task(intent.task_title, actor, intent.due_date,
                                     assignee_id, assignee_name)
            if assignee_id is not None:
                await message.reply(t(lang, "task_added", title=row["title"])
                                    + t(lang, "task_assigned_note", who=assignee_name),
                                    reply_markup=main_keyboard(lang))
                try:
                    await bot.send_message(assignee_id, t(
                        get_user_lang(conn, assignee_id), "task_new_dm",
                        who=actor, title=row["title"],
                        due=(f" {intent.due_date}" if intent.due_date else "")),
                        reply_markup=main_keyboard(get_user_lang(conn, assignee_id)))
                except Exception:
                    pass  # the task exists; a failed DM must not fail the reply
            else:
                note = t(lang, "task_unassigned_note", who=intent.assignee) \
                    if intent.assignee else ""
                await message.reply(t(lang, "task_added", title=row["title"]) + note,
                                    reply_markup=main_keyboard(lang))

        elif intent.action == "donetask":
            svc_tasks = services.get("tasks") or TaskService(conn)
            row = svc_tasks.complete(intent.medicine_query, actor_name(message.from_user))
            if row:
                await message.reply(t(lang, "task_done", title=row["title"]),
                                    reply_markup=main_keyboard(lang))
            else:
                # No exact match: offer fuzzy candidates (open tasks only).
                candidates = [r for r in fuzzy_matches(
                    conn, intent.medicine_query or text.strip(),
                    table="tasks") if not r["done"]]
                if candidates:
                    PENDING[(message.chat.id, tg_id)] = "donetask"
                    await reply_pick_buttons(message, candidates, 1, key="maybe",
                                             label_col="title")
                else:
                    await message.reply(t(lang, "no_match"),
                                        reply_markup=main_keyboard(lang))

        elif intent.action == "showtasks":
            svc_tasks = services.get("tasks") or TaskService(conn)
            rows = svc_tasks.list_open()
            body = format_open_tasks(rows, lang, datetime.date.today().isoformat())
            if body:
                await message.reply(body, reply_markup=main_keyboard(lang))
            else:
                await message.reply(t(lang, "task_empty"),
                                    reply_markup=main_keyboard(lang))

        # unknown: ignore unrecognized chatter

    @router.callback_query(F.data)
    async def on_callback(query: CallbackQuery, bot: Bot):
        try:
            data = query.data or ""

            if data.startswith("pick:"):
                # Parse before callback_to_action, which would crash on the
                # colon-separated format ("pick:12:1" is not an int).
                med_id, amount = parse_pick_data(data)
                tg_id = query.from_user.id
                actor = actor_name(query.from_user)
                chat_id = query.message.chat.id if query.message else 0
                pending = PENDING.pop((chat_id, tg_id), None) or "take"
                if query.message:
                    await do_action(query.message, tg_id, actor,
                                    pending, med_id, amount)
                await query.answer()
                return

            if data.startswith("setlang:"):
                # Template "🌐 Language" inline keyboard: change the user's
                # language (same UPDATE as /lang) and confirm in the new one.
                code = data.split(":", 1)[1]
                if code in LANG_CODES:
                    conn.execute(
                        "UPDATE allowed_users SET lang=? WHERE telegram_id=?",
                        (code, query.from_user.id))
                    conn.commit()
                    if query.message:
                        await query.message.reply(t(code, "language"))
                await query.answer()
                return

            action, val = callback_to_action(data)
            tg_id = query.from_user.id
            lang = get_user_lang(conn, tg_id)
            actor = actor_name(query.from_user)
            chat_id = query.message.chat.id if query.message else 0

            if action in ("approve", "decline"):
                if not is_admin(settings, tg_id):
                    return
                if action == "approve":
                    approve(conn, val)
                    if query.message:
                        try:
                            await query.message.edit_text("✅")
                        except Exception:
                            pass
                    # Approved users get the keyboard right away, even if the
                    # bot was never /started by them before approval existed.
                    await bot.send_message(val, t(DEFAULT_LANG, "approved"),
                                           reply_markup=main_keyboard(
                                               get_user_lang(conn, val)))
                else:
                    decline(conn, val)
                    if query.message:
                        try:
                            await query.message.edit_text("❌")
                        except Exception:
                            pass
                return

            if action == "discard":
                # Two-step: ask whether the item should also go on the
                # shopping list before actually discarding it.
                med = svc.get(val)
                if med is None:
                    if query.message:
                        await query.message.reply(t(lang, "no_match"))
                elif query.message:
                    kb = InlineKeyboardBuilder()
                    kb.button(text="🛒 " + t(lang, "discard_add"),
                              callback_data=f"discard_add:{val}")
                    kb.button(text="🗑 " + t(lang, "discard_only"),
                              callback_data=f"discard_only:{val}")
                    await query.message.reply(
                        t(lang, "discard_ask", name=med["name"]),
                        reply_markup=kb.as_markup())
            elif action == "discard_add":
                med = svc.get(val)
                if med is None:
                    if query.message:
                        await query.message.reply(t(lang, "no_match"))
                else:
                    name = med["name"]
                    svc_shop = services.get("shopping") or ShoppingService(conn)
                    svc_shop.add_items([name], actor, from_medicine_id=val)
                    svc.discard(val, actor)
                    if query.message:
                        await query.message.reply(t(lang, "discarded") + "\n"
                                                  + t(lang, "added_to_list"))
            elif action == "discard_only":
                if svc.get(val) is None:
                    if query.message:
                        await query.message.reply(t(lang, "no_match"))
                else:
                    svc.discard(val, actor)
                    if query.message:
                        await query.message.reply(t(lang, "discarded"))
            elif action == "snooze_expiry":
                until = (datetime.date.today()
                         + datetime.timedelta(days=30)).isoformat()
                conn.execute("UPDATE medicines SET snooze_expiry_until=? WHERE id=?",
                             (until, val))
                conn.commit()
                if query.message:
                    await query.message.reply(t(lang, "snoozed"))
            elif action == "snooze_opened":
                until = (datetime.date.today()
                         + datetime.timedelta(days=7)).isoformat()
                conn.execute("UPDATE medicines SET snooze_opened_until=? WHERE id=?",
                             (until, val))
                conn.commit()
                if query.message:
                    await query.message.reply(t(lang, "snoozed"))
            elif action == "addlist":
                med = svc.get(val)
                if med is None:
                    if query.message:
                        await query.message.reply(t(lang, "no_match"))
                else:
                    svc_shop = services.get("shopping") or ShoppingService(conn)
                    svc_shop.add_items([med["name"]], actor, from_medicine_id=val)
                    if query.message:
                        await query.message.reply(t(lang, "list_added",
                                                    items=med["name"]))
        except Exception:
            pass  # any error: just ack below
        finally:
            try:
                await query.answer()
            except Exception:
                pass

    return router
