import datetime, os
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.alerts import evaluate
from app.services.backup import run_backup
from app.bot.notify import alert_text, alert_keyboard
from app.i18n import t

async def run_daily_check(conn, settings, bot: Bot, now_date: str | None = None) -> int:
    today = now_date or datetime.date.today().isoformat()
    row = conn.execute("SELECT lang FROM allowed_users WHERE telegram_id=?",
                       (settings.admin_telegram_id,)).fetchone()
    lang = row["lang"] if row and row["lang"] else "pl"
    sent = 0
    for a in evaluate(conn, today):
        med = conn.execute("SELECT * FROM medicines WHERE id=?", (a.medicine_id,)).fetchone()
        await bot.send_message(settings.admin_telegram_id,
                               alert_text(lang, a, dict(med)),
                               reply_markup=alert_keyboard(a))
        sent += 1
        if a.kind.startswith("low_stock"):
            conn.execute("UPDATE medicines SET low_stock_notified=1 WHERE id=?", (a.medicine_id,))
    conn.commit()
    return sent

async def retry_needs_ai(conn, settings, extract_fn):
    rows = conn.execute("SELECT * FROM medicines WHERE ai_status='needs_ai_data' AND photo_path IS NOT NULL").fetchall()
    for r in rows:
        with open(r["photo_path"], "rb") as f:
            ext = await extract_fn(settings, [f.read()])
        if ext and getattr(ext, "name", ""):
            conn.execute(
                "UPDATE medicines SET name=?, expiry_date=?, ai_status='ok' WHERE id=?",
                (ext.name, ext.expiry_date, r["id"]))
    conn.commit()

def schedule_jobs(conn, settings, bot: Bot, scheduler: AsyncIOScheduler, extract_fn):
    scheduler.add_job(run_daily_check, "cron", hour=settings.daily_check_hour, minute=0,
                      args=[conn, settings, bot], id="daily_check", replace_existing=True)
    scheduler.add_job(retry_needs_ai, "interval", hours=1,
                      args=[conn, settings, extract_fn], id="ai_retry", replace_existing=True)
    scheduler.add_job(run_backup, "cron", hour=3, minute=0,
                      args=[os.path.join(settings.data_dir, "hub.db"),
                            os.path.join(settings.data_dir, "backups"),
                            settings.backup_keep_days],
                      id="backup", replace_existing=True)
