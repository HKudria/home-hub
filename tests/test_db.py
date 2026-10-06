import tempfile
import unittest
from pathlib import Path

from app.db import init_db


class TestDb(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db_path = str(Path(tmp.name) / "hub.db")

    def test_init_db_creates_tables(self):
        conn = init_db(self.db_path)
        self.addCleanup(conn.close)
        names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertLessEqual({"medicines", "events", "allowed_users"}, names)

    def test_medicines_defaults(self):
        conn = init_db(self.db_path)
        self.addCleanup(conn.close)
        conn.execute(
            "INSERT INTO medicines (name) VALUES (?)", ("Test",))
        row = conn.execute("SELECT * FROM medicines").fetchone()
        self.assertEqual(row["quantity"], 0)
        self.assertEqual(row["low_stock_threshold"], 3)
        self.assertEqual(row["ai_status"], "needs_ai_data")
        self.assertEqual(row["unit"], "pieces")


if __name__ == "__main__":
    unittest.main()
