import datetime, os, re
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.alerts import evaluate
from app.services.backup import run_backup
from app.services.task_service import TaskService
from app.bot.notify import alert_text, alert_keyboard
from app.bot.router import format_open_tasks, get_user_lang
from app.i18n import t

_FULL_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

async def run_daily_check(conn, settings, bot: Bot, now_date: str | None = None) -> int:
    today = now_date or datetime.date.today().isoformat()
    row = conn.execute("SELECT lang FROM allowed_users WHERE telegram_id=?",
                       (settings.admin_telegram_id,)).fetchone()
    lang = row["lang"] if row and row["lang"] else "pl"
    sent = 0
    for a in evaluate(conn, today):
        med = conn.execute("SELECT * FROM medicines WHERE id=?", (a.medicine_id,)).fetchone()
        try:
            await bot.send_message(settings.admin_telegram_id,
                                   alert_text(lang, a, dict(med)),
                                   reply_markup=alert_keyboard(a))
        except Exception:
            continue  # one failed send must not block the remaining alerts
        sent += 1
        if a.kind.startswith("low_stock"):
            conn.execute("UPDATE medicines SET low_stock_notified=1 WHERE id=?", (a.medicine_id,))
    conn.commit()
    return sent

async def run_task_digest(conn, settings, bot: Bot, today: str | None = None) -> int:
    """Daily digest of due/overdue tasks: full list to the admin, each
    assignee gets their own list. Returns the number of sends that
    succeeded."""
    today = today or datetime.date.today().isoformat()
    svc = TaskService(conn)
    rows = svc.due_and_overdue(today)
    if not rows:
        return 0
    sent = 0
    lang = get_user_lang(conn, settings.admin_telegram_id)
    try:
        await bot.send_message(settings.admin_telegram_id,
                               t(lang, "task_digest") + "\n"
                               + format_open_tasks(rows, lang, today))
        sent += 1
    except Exception:
        pass  # one failed send must not block the assignee digests
    assignee_ids = sorted({r["assignee_id"] for r in rows
                           if r["assignee_id"]
                           and r["assignee_id"] != settings.admin_telegram_id})
    for tg_id in assignee_ids:
        own = svc.for_assignee(tg_id, today)
        own_lang = get_user_lang(conn, tg_id)
        try:
            await bot.send_message(tg_id, t(own_lang, "task_digest") + "\n"
                                   + format_open_tasks(own, own_lang, today))
            sent += 1
        except Exception:
            continue
    return sent

async def retry_needs_ai(conn, settings, extract_fn):
    rows = conn.execute("SELECT * FROM medicines WHERE ai_status='needs_ai_data' AND photo_path IS NOT NULL").fetchall()
    for r in rows:
        try:
            path = r["photo_path"] if os.path.isabs(r["photo_path"]) \
                else os.path.join(settings.data_dir, r["photo_path"])
            with open(path, "rb") as f:
                ext = await extract_fn(settings, [f.read()])
            if ext and getattr(ext, "name", ""):
                updates = {"name": ext.name, "ai_status": "ok"}
                # Only overwrite the expiry with a full ISO date; partial
                # values like "2027-03" would break date handling everywhere.
                if getattr(ext, "expiry_date", None) and _FULL_DATE.match(ext.expiry_date):
                    updates["expiry_date"] = ext.expiry_date
                conn.execute(
                    "UPDATE medicines SET name=?, ai_status=?, expiry_date=? WHERE id=?",
                    (updates["name"], updates["ai_status"],
                     updates.get("expiry_date", r["expiry_date"]), r["id"]))
        except Exception:
            continue  # a bad row (missing file, AI error) must not kill the rest
    conn.commit()

def schedule_jobs(conn, settings, bot: Bot, scheduler: AsyncIOScheduler, extract_fn):
    scheduler.add_job(run_daily_check, "cron", hour=settings.daily_check_hour, minute=0,
                      args=[conn, settings, bot], id="daily_check", replace_existing=True)
    scheduler.add_job(run_task_digest, "cron", hour=settings.daily_check_hour, minute=0,
                      args=[conn, settings, bot], id="task_digest", replace_existing=True)
    scheduler.add_job(retry_needs_ai, "interval", hours=1,
                      args=[conn, settings, extract_fn], id="ai_retry", replace_existing=True)
    scheduler.add_job(run_backup, "cron", hour=3, minute=0,
                      args=[os.path.join(settings.data_dir, "hub.db"),
                            os.path.join(settings.data_dir, "backups"),
                            settings.backup_keep_days],
                      id="backup", replace_existing=True)
