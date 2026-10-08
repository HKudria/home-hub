import tempfile
import unittest

from app.db import init_db
from app.services.task_service import TaskService


class TaskServiceTest(unittest.TestCase):
    def make_svc(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conn = init_db(f"{tmp.name}/t.db")
        self.addCleanup(conn.close)
        return TaskService(conn), conn

    def test_add_returns_row_with_trimmed_title(self):
        svc, conn = self.make_svc()
        row = svc.add_task("  Kup mleko  ", actor="herman")
        self.assertIsNotNone(row)
        self.assertEqual(row["title"], "Kup mleko")
        self.assertEqual(row["created_by"], "herman")
        self.assertEqual(row["done"], 0)
        self.assertIsNone(row["due_date"])
        self.assertIsNone(row["assignee_id"])
        self.assertIsNone(row["assignee_name"])
        stored = conn.execute("SELECT * FROM tasks WHERE id=?", (row["id"],)).fetchone()
        self.assertEqual(stored["title"], "Kup mleko")

    def test_add_stores_due_date_verbatim_and_assignee(self):
        svc, _ = self.make_svc()
        row = svc.add_task("Zebrać opakowania", actor="herman",
                           due_date="2026-10-10", assignee_id=42, assignee_name="Zoe")
        self.assertEqual(row["due_date"], "2026-10-10")
        self.assertEqual(row["assignee_id"], 42)
        self.assertEqual(row["assignee_name"], "Zoe")
        row = svc.add_task("No due", actor="herman")
        self.assertIsNone(row["due_date"])

    def test_add_empty_or_whitespace_title_raises(self):
        svc, conn = self.make_svc()
        with self.assertRaises(ValueError):
            svc.add_task("", actor="herman")
        with self.assertRaises(ValueError):
            svc.add_task("   ", actor="herman")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 0)

    def test_list_open_orders_due_asc_nulls_last_then_id(self):
        svc, _ = self.make_svc()
        svc.add_task("B later", actor="herman", due_date="2026-10-08")
        svc.add_task("No due", actor="herman")
        svc.add_task("A later", actor="herman", due_date="2026-10-08")
        svc.add_task("Early", actor="herman", due_date="2026-09-01")
        rows = svc.list_open()
        self.assertEqual(
            [r["title"] for r in rows],
            ["Early", "B later", "A later", "No due"])

    def test_complete_by_title_unicode_fold(self):
        svc, _ = self.make_svc()
        svc.add_task("Żółtko", actor="herman")
        row = svc.complete("żółtko", actor="zoe")
        self.assertIsNotNone(row)
        self.assertEqual(row["done"], 1)
        self.assertEqual(row["done_by"], "zoe")
        self.assertIsNotNone(row["done_at"])
        self.assertEqual([t["title"] for t in svc.list_open()], [])

    def test_complete_by_id(self):
        svc, _ = self.make_svc()
        svc.add_task("Kup mleko", actor="herman")
        task_id = svc.list_open()[0]["id"]
        row = svc.complete(str(task_id), actor="herman")
        self.assertIsNotNone(row)
        self.assertEqual(row["id"], task_id)
        self.assertEqual(row["done"], 1)
        self.assertEqual(row["done_by"], "herman")
        self.assertIsNotNone(row["done_at"])

    def test_complete_missing_returns_none(self):
        svc, _ = self.make_svc()
        svc.add_task("Kup mleko", actor="herman")
        self.assertIsNone(svc.complete("Nie ma takiego zadania", actor="herman"))
        self.assertIsNone(svc.complete("999", actor="herman"))

    def test_complete_only_matches_open_tasks(self):
        svc, _ = self.make_svc()
        svc.add_task("Kup mleko", actor="herman")
        svc.complete("Kup mleko", actor="herman")
        self.assertIsNone(svc.complete("kup mleko", actor="herman"))
        task_id = svc.list_done()[0]["id"]
        self.assertIsNone(svc.complete(str(task_id), actor="herman"))

    def test_toggle_completes_then_reopens(self):
        svc, conn = self.make_svc()
        svc.add_task("Kup mleko", actor="herman")
        task_id = svc.list_open()[0]["id"]
        row = svc.toggle(task_id, actor="zoe")
        self.assertIsNotNone(row)
        self.assertEqual(row["done"], 1)
        self.assertEqual(row["done_by"], "zoe")
        self.assertIsNotNone(row["done_at"])
        row = svc.toggle(task_id, actor="zoe")
        self.assertIsNotNone(row)
        self.assertEqual(row["done"], 0)
        self.assertIsNone(row["done_by"])
        self.assertIsNone(row["done_at"])
        self.assertEqual([t["title"] for t in svc.list_open()], ["Kup mleko"])

    def test_toggle_missing_returns_none(self):
        svc, _ = self.make_svc()
        self.assertIsNone(svc.toggle(999, actor="herman"))

    def test_list_done_newest_first_with_limit(self):
        svc, conn = self.make_svc()
        svc.add_task("A", actor="herman")
        svc.add_task("B", actor="herman")
        a_id = svc.list_open()[0]["id"]
        b_id = svc.list_open()[1]["id"]
        svc.complete(str(a_id), actor="herman")
        svc.complete(str(b_id), actor="herman")
        conn.execute("UPDATE tasks SET done_at='2026-10-08 09:00:00' WHERE id=?", (a_id,))
        conn.execute("UPDATE tasks SET done_at='2026-10-08 10:00:00' WHERE id=?", (b_id,))
        conn.commit()
        rows = svc.list_done()
        self.assertEqual([r["title"] for r in rows], ["B", "A"])
        self.assertEqual([r["title"] for r in svc.list_done(limit=1)], ["B"])

    def test_due_and_overdue_boundary(self):
        svc, _ = self.make_svc()
        svc.add_task("Due today", actor="herman", due_date="2026-10-08")
        svc.add_task("Due tomorrow", actor="herman", due_date="2026-10-09")
        svc.add_task("Overdue", actor="herman", due_date="2026-10-01")
        svc.add_task("No due", actor="herman")
        overdue = svc.add_task("Done and overdue", actor="herman", due_date="2026-09-15")
        svc.complete(str(overdue["id"]), actor="herman")
        rows = svc.due_and_overdue("2026-10-08")
        self.assertEqual(
            [r["title"] for r in rows], ["Overdue", "Due today"])

    def test_for_assignee_filter(self):
        svc, _ = self.make_svc()
        svc.add_task("Mine today", actor="herman", due_date="2026-10-08",
                     assignee_id=42, assignee_name="Zoe")
        svc.add_task("Mine tomorrow", actor="herman", due_date="2026-10-09",
                     assignee_id=42, assignee_name="Zoe")
        svc.add_task("Mine no due", actor="herman", assignee_id=42, assignee_name="Zoe")
        svc.add_task("Theirs", actor="herman", due_date="2026-10-08",
                     assignee_id=43, assignee_name="Bo")
        svc.add_task("Unassigned", actor="herman", due_date="2026-10-08")
        mine = svc.add_task("Mine done", actor="herman", due_date="2026-10-01",
                            assignee_id=42, assignee_name="Zoe")
        svc.complete(str(mine["id"]), actor="herman")
        rows = svc.for_assignee(42, "2026-10-08")
        self.assertEqual([r["title"] for r in rows], ["Mine today"])


if __name__ == "__main__":
    unittest.main()
