import sqlite3
from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder

def is_admin(settings, tg_id: int) -> bool:
    return tg_id == settings.admin_telegram_id

def is_allowed(conn: sqlite3.Connection, tg_id: int) -> bool:
    row = conn.execute("SELECT role FROM allowed_users WHERE telegram_id=?", (tg_id,)).fetchone()
    return row is not None and row["role"] == "member"

async def request_approval(conn, settings, bot: Bot, tg_id: int, name: str):
    conn.execute("INSERT OR IGNORE INTO allowed_users (telegram_id, name, role) VALUES (?,?, 'pending')",
                 (tg_id, name))
    conn.commit()
    kb = InlineKeyboardBuilder()
    kb.button(text="✅", callback_data=f"approve:{tg_id}")
    kb.button(text="❌", callback_data=f"decline:{tg_id}")
    await bot.send_message(settings.admin_telegram_id,
                           f"User {name} ({tg_id}) asks for access.", reply_markup=kb.as_markup())

def approve(conn, tg_id: int):
    conn.execute("UPDATE allowed_users SET role='member' WHERE telegram_id=?", (tg_id,))
    conn.commit()

def decline(conn, tg_id: int):
    conn.execute("DELETE FROM allowed_users WHERE telegram_id=?", (tg_id,))
    conn.commit()
