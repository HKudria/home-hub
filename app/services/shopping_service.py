import sqlite3


class ShoppingService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def add_items(self, names: list, actor: str, from_medicine_id: int | None = None) -> list:
        trimmed = [n.strip() for n in names]
        trimmed = [n for n in trimmed if n]
        existing = {
            row["name"].lower()
            for row in self.conn.execute("SELECT name FROM shopping_items WHERE bought=0")
        }
        added = []
        for name in trimmed:
            key = name.lower()
            if key in existing:
                continue
            self.conn.execute(
                "INSERT INTO shopping_items (name, added_by, from_medicine_id) VALUES (?,?,?)",
                (name, actor, from_medicine_id))
            existing.add(key)
            added.append(name)
        self.conn.commit()
        return added

    def list_unbought(self) -> list:
        return self.conn.execute(
            "SELECT * FROM shopping_items WHERE bought=0 ORDER BY id").fetchall()

    def list_bought(self, limit: int = 20) -> list:
        return self.conn.execute(
            "SELECT * FROM shopping_items WHERE bought=1 "
            "ORDER BY bought_at DESC, id DESC LIMIT ?", (limit,)).fetchall()

    def check_off(self, query: str, actor: str):
        if query.isdigit():
            row = self.conn.execute(
                "SELECT * FROM shopping_items WHERE id=? AND bought=0",
                (int(query),)).fetchone()
        else:
            key = query.strip().lower()
            row = next(
                (u for u in self.list_unbought() if u["name"].lower() == key), None)
        if row is None:
            return None
        self.conn.execute(
            "UPDATE shopping_items SET bought=1, bought_by=?, bought_at=datetime('now') "
            "WHERE id=?", (actor, row["id"]))
        self.conn.commit()
        return self.conn.execute(
            "SELECT * FROM shopping_items WHERE id=?", (row["id"],)).fetchone()

    def uncheck(self, item_id: int):
        self.conn.execute(
            "UPDATE shopping_items SET bought=0, bought_by=NULL, bought_at=NULL WHERE id=?",
            (item_id,))
        self.conn.commit()

    def clear_bought(self) -> int:
        cur = self.conn.execute("DELETE FROM shopping_items WHERE bought=1")
        self.conn.commit()
        return cur.rowcount

    def recent_activity(self, limit: int = 15) -> list:
        return self.conn.execute(
            "SELECT * FROM shopping_items "
            "ORDER BY COALESCE(bought_at, added_at) DESC LIMIT ?", (limit,)).fetchall()
