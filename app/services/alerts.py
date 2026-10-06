import datetime
from dataclasses import dataclass

@dataclass
class Alert:
    kind: str
    medicine_id: int
    name: str
    days: int

def _d(s: str) -> datetime.date:
    return datetime.date.fromisoformat(s)

def evaluate(conn, today: str) -> list[Alert]:
    t = _d(today)
    out = []
    for m in conn.execute("SELECT * FROM medicines").fetchall():
        if m["expiry_date"] and not (m["snooze_expiry_until"] and t <= _d(m["snooze_expiry_until"])):
            expiry = _d(m["expiry_date"])
            d = (expiry - t).days
            snooze_end = _d(m["snooze_expiry_until"]) if m["snooze_expiry_until"] else None
            if snooze_end and snooze_end >= expiry:
                # Snooze ran past the expiry date: re-fire once on the
                # first day after the snooze ends.
                if t == snooze_end + datetime.timedelta(days=1):
                    out.append(Alert("expired", m["id"], m["name"], d))
            elif d == 7:
                out.append(Alert("expiry_soon", m["id"], m["name"], d))
            elif d == 0:
                out.append(Alert("expiry_today", m["id"], m["name"], d))
            elif d < 0 and (-d) % 30 == 0:
                out.append(Alert("expired", m["id"], m["name"], d))
        if m["opened_at"] and m["discard_after_days"] and not (
                m["snooze_opened_until"] and t <= _d(m["snooze_opened_until"])):
            discard = _d(m["opened_at"]) + datetime.timedelta(days=m["discard_after_days"])
            d = (discard - t).days
            snooze_end = _d(m["snooze_opened_until"]) if m["snooze_opened_until"] else None
            if snooze_end and snooze_end >= discard:
                # Snooze ran past the discard date: re-fire once on the
                # first day after the snooze ends.
                if t == snooze_end + datetime.timedelta(days=1):
                    out.append(Alert("opened_today", m["id"], m["name"], d))
            elif d == 1:
                out.append(Alert("opened_soon", m["id"], m["name"], d))
            elif d == 0:
                out.append(Alert("opened_today", m["id"], m["name"], d))
        if (m["low_stock_threshold"] > 0 and m["quantity"] <= m["low_stock_threshold"]
                and not m["low_stock_notified"]):
            kind = "low_stock_last" if m["quantity"] == 0 else "low_stock"
            out.append(Alert(kind, m["id"], m["name"], int(m["quantity"])))
    return out
