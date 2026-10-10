import sqlite3

COLUMNS = [
    "name", "active_ingredient", "form",
    "dosage_pl", "dosage_ru", "dosage_uk", "dosage_en",
    "description_pl", "description_ru", "description_uk", "description_en",
    "expiry_date", "opened_at", "discard_after_days", "quantity", "unit",
    "low_stock_threshold", "photo_path", "ai_status",
    "snooze_expiry_until", "snooze_opened_until",
]

class MedicineService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def add(self, fields: dict) -> int:
        fields = {k: v for k, v in fields.items() if k in COLUMNS}
        fields.setdefault("ai_status", "ok")
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        cur = self.conn.execute(
            f"INSERT INTO medicines ({cols}) VALUES ({marks})", list(fields.values()))
        self.conn.commit()
        return cur.lastrowid

    def get(self, medicine_id: int):
        return self.conn.execute(
            "SELECT * FROM medicines WHERE id=?", (medicine_id,)).fetchone()

    def list_all(self):
        return self.conn.execute(
            "SELECT * FROM medicines ORDER BY (expiry_date IS NULL), expiry_date").fetchall()

    def update(self, medicine_id: int, fields: dict):
        fields = {k: v for k, v in fields.items() if k in COLUMNS}
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        self.conn.execute(
            f"UPDATE medicines SET {sets}, updated_at=datetime('now') WHERE id=?",
            [*fields.values(), medicine_id])
        self.conn.commit()

    def _event(self, medicine_id: int, actor: str, delta: float, note: str = ""):
        self.conn.execute(
            "INSERT INTO events (medicine_id, actor, delta, note) VALUES (?,?,?,?)",
            (medicine_id, actor, delta, note))

    def take_dose(self, medicine_id: int, amount: float, actor: str):
        row = self.get(medicine_id)
        if row is None:
            return None
        new_q = max(0.0, row["quantity"] - amount)
        reset = new_q > row["quantity"]
        self.conn.execute(
            "UPDATE medicines SET quantity=?, low_stock_notified=?, updated_at=datetime('now') WHERE id=?",
            (new_q, 0 if reset else row["low_stock_notified"], medicine_id))
        self._event(medicine_id, actor, -amount)
        self.conn.commit()
        return self.get(medicine_id)

    def mark_opened(self, medicine_id: int, day: str, actor: str):
        self.update(medicine_id, {"opened_at": day})
        self._event(medicine_id, actor, 0, "opened")
        self.conn.commit()

    def discard(self, medicine_id: int, actor: str):
        # Events must go first (immediate FK enforcement), then the medicine.
        self.conn.execute("DELETE FROM events WHERE medicine_id=?", (medicine_id,))
        self.conn.execute("DELETE FROM medicines WHERE id=?", (medicine_id,))
        self.conn.commit()

    def recent_events(self, limit: int = 20):
        return self.conn.execute(
            "SELECT e.*, m.name FROM events e JOIN medicines m ON m.id=e.medicine_id "
            "ORDER BY e.id DESC LIMIT ?", (limit,)).fetchall()
