"""Telegram router: commands, free-text intent dispatch, callback handling.

`build_router(conn, settings, services)` wires every handler against the
shared sqlite connection and the services dict ({"medicines": MedicineService}).
"""

import datetime
import json
import re
import sqlite3

import httpx
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.ai.interpret import Intent, interpret
from app.bot.notify import callback_to_action
from app.bot.users import approve, decline, is_admin, is_allowed, request_approval
from app.config import Settings
from app.i18n import DEFAULT_LANG, t
from app.services.medicine_service import MedicineService

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


def _like_all(conn: sqlite3.Connection, term: str) -> list:
    q = f"%{term.lower()}%"
    return conn.execute(
        "SELECT * FROM medicines WHERE lower(name) LIKE ? OR lower(active_ingredient) LIKE ? "
        "OR lower(description_en) LIKE ? OR lower(description_pl) LIKE ? "
        "OR lower(description_ru) LIKE ? OR lower(description_uk) LIKE ?",
        (q, q, q, q, q, q)).fetchall()


def symptom_matches(conn: sqlite3.Connection, symptom: str) -> list:
    rows = {r["id"]: r for r in _like_all(conn, symptom)}
    for term in SYMPTOM_SYNONYMS.get(symptom.lower().strip(), []):
        for r in _like_all(conn, term):
            rows.setdefault(r["id"], r)
    return [rows[k] for k in sorted(rows)]


def describe_matches(rows, lang: str) -> str:
    lines = []
    for r in rows:
        lines.append(f"• {r['name']} — {int(r['quantity'])} {r['unit']}")
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
        lines.append(f"• {r['name']} — {int(r['quantity'])} {r['unit']}{mark}")
    return "\n".join(lines)


def parse_pick_data(data: str):
    """Return (medicine_id, amount) from 'pick:<id>:<amount>'."""
    parts = data.split(":")
    return int(parts[1]), float(parts[2]) if len(parts) > 2 and parts[2] else 1.0


def get_user_lang(conn: sqlite3.Connection, tg_id: int) -> str:
    row = conn.execute("SELECT lang FROM allowed_users WHERE telegram_id=?", (tg_id,)).fetchone()
    if row and row["lang"] in LANG_CODES:
        return row["lang"]
    return DEFAULT_LANG


def actor_name(user) -> str:
    if user is None:
        return ""
    return user.full_name or (f"@{user.username}" if user.username else "")


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
        row = svc.get(med_id)
        if row is None:
            await message.reply(t(lang, "no_match"))
            return
        if action == "take":
            row = svc.take_dose(med_id, amount, actor)
            if row is None:
                await message.reply(t(lang, "no_match"))
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
                await message.reply(t(lang, "last_dose", name=row["name"]))
            else:
                await message.reply(t(lang, "took", name=row["name"],
                                      qty=int(row["quantity"]), unit=row["unit"]))
        elif action == "opened":
            today = datetime.date.today().isoformat()
            svc.mark_opened(med_id, today, actor)
            await message.reply(t(lang, "opened_on", name=row["name"], opened=today))
        elif action == "query_qty":
            await message.reply(t(lang, "took", name=row["name"],
                                  qty=int(row["quantity"]), unit=row["unit"]))

    async def reply_pick_buttons(message: Message, rows, amount: float):
        kb = InlineKeyboardBuilder()
        for r in rows:
            kb.button(text=r["name"], callback_data=f"pick:{r['id']}:{int(amount)}")
        await message.reply(t(get_user_lang(conn, message.from_user.id), "which_one"),
                            reply_markup=kb.as_markup())

    @router.message(Command("start"))
    async def cmd_start(message: Message, bot: Bot):
        tg_id = message.from_user.id
        lang = get_user_lang(conn, tg_id)
        if is_admin(settings, tg_id) or is_allowed(conn, tg_id):
            await message.reply(t(lang, "approved"))
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
        intent = await interpret(settings, text)

        if intent.action in ("take", "opened", "query_qty"):
            query = intent.medicine_query or text.strip()
            rows = match_medicines(conn, query)
            amount = intent.amount if intent.action == "take" else 1
            if not rows:
                await message.reply(t(lang, "no_match"))
            elif len(rows) > 1:
                PENDING[(message.chat.id, tg_id)] = intent.action
                await reply_pick_buttons(message, rows, amount)
            else:
                await do_action(message, tg_id, actor_name(message.from_user),
                                intent.action, rows[0]["id"], amount)

        elif intent.action == "expiring":
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
                await message.reply(t(lang, "symptom_none"))
            else:
                lines = [t(lang, "expiring_soon_list")]
                lines += [f"• {r['name']} — {r['expiry_date']}" for r in soon]
                await message.reply("\n".join(lines))

        elif intent.action == "symptom":
            symptom = intent.symptom or text.strip()
            terms = [symptom]
            try:
                terms += await symptom_terms(settings, symptom)
            except Exception:
                pass
            by_id: dict[int, sqlite3.Row] = {}
            for term in terms:
                if not term:
                    continue
                for r in symptom_matches(conn, term):
                    by_id.setdefault(r["id"], r)
            rows = [by_id[k] for k in sorted(by_id)]
            if not rows:
                await message.reply(t(lang, "symptom_none"))
            else:
                await message.reply(t(lang, "symptom_found") + "\n"
                                    + describe_matches_enhanced(rows, lang))

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
                    await bot.send_message(val, t(DEFAULT_LANG, "approved"))
                else:
                    decline(conn, val)
                    if query.message:
                        try:
                            await query.message.edit_text("❌")
                        except Exception:
                            pass
                return

            if action == "discard":
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
                conn.execute(
                    "INSERT INTO events (medicine_id, actor, delta, note) VALUES (?,?,0,'shopping_list')",
                    (val, actor))
                conn.commit()
                if query.message:
                    await query.message.reply(t(lang, "added_to_list"))
        except Exception:
            pass  # any error: just ack below
        finally:
            try:
                await query.answer()
            except Exception:
                pass

    return router
