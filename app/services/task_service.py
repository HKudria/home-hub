import sqlite3


class TaskService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def add_task(self, title: str, actor: str, due_date: str | None = None,
                 assignee_id: int | None = None,
                 assignee_name: str | None = None):
        trimmed = title.strip()
        if not trimmed:
            raise ValueError("task title must not be empty")
        cur = self.conn.execute(
            "INSERT INTO tasks (title, created_by, due_date, assignee_id, assignee_name) "
            "VALUES (?,?,?,?,?)",
            (trimmed, actor, due_date, assignee_id, assignee_name))
        self.conn.commit()
        return self.conn.execute(
            "SELECT * FROM tasks WHERE id=?", (cur.lastrowid,)).fetchone()

    def list_open(self) -> list:
        return self.conn.execute(
            "SELECT * FROM tasks WHERE done=0 "
            "ORDER BY (due_date IS NULL), due_date, id").fetchall()

    def list_done(self, limit: int = 20) -> list:
        return self.conn.execute(
            "SELECT * FROM tasks WHERE done=1 "
            "ORDER BY done_at DESC, id DESC LIMIT ?", (limit,)).fetchall()

    def complete(self, query: str, actor: str):
        if query.isdigit():
            row = self.conn.execute(
                "SELECT * FROM tasks WHERE id=? AND done=0",
                (int(query),)).fetchone()
        else:
            key = query.strip().lower()
            row = next(
                (t for t in self.list_open() if t["title"].lower() == key), None)
        if row is None:
            return None
        self.conn.execute(
            "UPDATE tasks SET done=1, done_by=?, done_at=datetime('now') WHERE id=?",
            (actor, row["id"]))
        self.conn.commit()
        return self.conn.execute(
            "SELECT * FROM tasks WHERE id=?", (row["id"],)).fetchone()

    def toggle(self, task_id: int, actor: str):
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            return None
        if row["done"]:
            self.conn.execute(
                "UPDATE tasks SET done=0, done_by=NULL, done_at=NULL WHERE id=?",
                (task_id,))
        else:
            self.conn.execute(
                "UPDATE tasks SET done=1, done_by=?, done_at=datetime('now') "
                "WHERE id=?", (actor, task_id))
        self.conn.commit()
        return self.conn.execute(
            "SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()

    def assign(self, task_id: int, telegram_id: int, name: str):
        self.conn.execute(
            "UPDATE tasks SET assignee_id=?, assignee_name=? WHERE id=?",
            (telegram_id, name, task_id))
        self.conn.commit()
        return self.conn.execute(
            "SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()

    def due_and_overdue(self, today: str) -> list:
        return self.conn.execute(
            "SELECT * FROM tasks WHERE done=0 AND due_date IS NOT NULL AND due_date <= ? "
            "ORDER BY due_date, id", (today,)).fetchall()

    def for_assignee(self, telegram_id: int, today: str) -> list:
        return self.conn.execute(
            "SELECT * FROM tasks WHERE done=0 AND assignee_id=? "
            "AND due_date IS NOT NULL AND due_date <= ? "
            "ORDER BY due_date, id", (telegram_id, today)).fetchall()
