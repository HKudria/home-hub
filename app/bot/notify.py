from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.services.alerts import Alert
from app.i18n import t

def alert_text(lang: str, alert: Alert, med: dict) -> str:
    med = dict(med)
    if alert.kind == "expiry_soon":
        return t(lang, "expires_in_days", name=alert.name, days=alert.days)
    if alert.kind == "expiry_today":
        return t(lang, "expires_today", name=alert.name)
    if alert.kind == "expired":
        return t(lang, "expired_days_ago", name=alert.name, days=-alert.days)
    if alert.kind == "opened_soon":
        return t(lang, "discard_soon", name=alert.name, opened=med.get("opened_at", ""))
    if alert.kind == "opened_today":
        return t(lang, "discard_today", name=alert.name, opened=med.get("opened_at", ""))
    if alert.kind == "low_stock":
        return t(lang, "low_stock", name=alert.name, qty=alert.days)
    return t(lang, "last_dose", name=alert.name)

def alert_keyboard(alert: Alert):
    kb = InlineKeyboardBuilder()
    if alert.kind in ("expiry_soon", "expiry_today", "expired"):
        kb.button(text="🗑", callback_data=f"discard:{alert.medicine_id}")
        kb.button(text="⏰", callback_data=f"snooze_expiry:{alert.medicine_id}")
    elif alert.kind.startswith("opened"):
        kb.button(text="🗑", callback_data=f"discard:{alert.medicine_id}")
        kb.button(text="⏰", callback_data=f"snooze_opened:{alert.medicine_id}")
    else:
        kb.button(text="🛒", callback_data=f"addlist:{alert.medicine_id}:")
    return kb.as_markup()

def callback_to_action(data: str) -> tuple[str, int]:
    action, rest = data.split(":", 1)
    return action, int(rest.rstrip(":"))
