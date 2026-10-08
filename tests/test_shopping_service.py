import tempfile
import unittest

from app.db import init_db
from app.services.shopping_service import ShoppingService


class ShoppingServiceTest(unittest.TestCase):
    def make_svc(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conn = init_db(f"{tmp.name}/t.db")
        self.addCleanup(conn.close)
        return ShoppingService(conn), conn

    def test_add_single(self):
        svc, conn = self.make_svc()
        added = svc.add_items(["Paracetamol"], actor="herman")
        self.assertEqual(added, ["Paracetamol"])
        row = conn.execute("SELECT * FROM shopping_items").fetchone()
        self.assertEqual(row["name"], "Paracetamol")
        self.assertEqual(row["added_by"], "herman")
        self.assertIsNone(row["from_medicine_id"])

    def test_add_with_from_medicine_id(self):
        svc, conn = self.make_svc()
        added = svc.add_items(["Ibuprofen"], actor="herman", from_medicine_id=7)
        self.assertEqual(added, ["Ibuprofen"])
        row = conn.execute("SELECT * FROM shopping_items").fetchone()
        self.assertEqual(row["from_medicine_id"], 7)

    def test_add_trims_and_drops_empties(self):
        svc, _ = self.make_svc()
        added = svc.add_items(["  Milk  ", "", "   "], actor="herman")
        self.assertEqual(added, ["Milk"])

    def test_add_dedupes_within_call_and_against_unbought(self):
        svc, _ = self.make_svc()
        first = svc.add_items(["Milk", "milk", "  MILK "], actor="herman")
        self.assertEqual(first, ["Milk"])
        second = svc.add_items(["milk"], actor="herman")
        self.assertEqual(second, [])
        # bought item no longer blocks re-adding
        svc.check_off("Milk", actor="herman")
        third = svc.add_items(["Milk"], actor="herman")
        self.assertEqual(third, ["Milk"])

    def test_list_unbought_oldest_first(self):
        svc, conn = self.make_svc()
        svc.add_items(["A", "B", "C"], actor="herman")
        conn.execute("UPDATE shopping_items SET added_at='2026-10-08 09:00:00' WHERE name='A'")
        conn.execute("UPDATE shopping_items SET added_at='2026-10-08 10:00:00' WHERE name='B'")
        conn.execute("UPDATE shopping_items SET added_at='2026-10-08 11:00:00' WHERE name='C'")
        conn.commit()
        rows = svc.list_unbought()
        self.assertEqual([r["name"] for r in rows], ["A", "B", "C"])

    def test_check_off_by_name_case_insensitive(self):
        svc, _ = self.make_svc()
        svc.add_items(["Milk"], actor="herman")
        row = svc.check_off("milk", actor="zoe")
        self.assertIsNotNone(row)
        self.assertEqual(row["bought"], 1)
        self.assertEqual(row["bought_by"], "zoe")
        self.assertIsNotNone(row["bought_at"])

    def test_check_off_unicode_case(self):
        svc, _ = self.make_svc()
        svc.add_items(["Żółtko"], actor="herman")
        row = svc.check_off("żółtko", actor="zoe")
        self.assertIsNotNone(row)
        self.assertEqual(row["bought"], 1)

    def test_check_off_by_id(self):
        svc, _ = self.make_svc()
        svc.add_items(["Milk"], actor="herman")
        item_id = svc.list_unbought()[0]["id"]
        row = svc.check_off(str(item_id), actor="herman")
        self.assertIsNotNone(row)
        self.assertEqual(row["id"], item_id)
        self.assertEqual(row["bought"], 1)

    def test_check_off_missing_returns_none(self):
        svc, _ = self.make_svc()
        svc.add_items(["Milk"], actor="herman")
        self.assertIsNone(svc.check_off("Bread", actor="herman"))
        self.assertIsNone(svc.check_off("999", actor="herman"))

    def test_check_off_only_matches_unbought(self):
        svc, _ = self.make_svc()
        svc.add_items(["Milk"], actor="herman")
        svc.check_off("Milk", actor="herman")
        self.assertIsNone(svc.check_off("milk", actor="herman"))

    def test_uncheck_resets_fields(self):
        svc, conn = self.make_svc()
        svc.add_items(["Milk"], actor="herman")
        item_id = svc.list_unbought()[0]["id"]
        svc.check_off(str(item_id), actor="zoe")
        svc.uncheck(item_id)
        row = conn.execute("SELECT * FROM shopping_items WHERE id=?", (item_id,)).fetchone()
        self.assertEqual(row["bought"], 0)
        self.assertIsNone(row["bought_by"])
        self.assertIsNone(row["bought_at"])
        self.assertEqual([r["name"] for r in svc.list_unbought()], ["Milk"])

    def test_list_bought_newest_first(self):
        svc, conn = self.make_svc()
        svc.add_items(["A", "B"], actor="herman")
        a_id = svc.list_unbought()[0]["id"]
        b_id = svc.list_unbought()[1]["id"]
        svc.check_off(str(a_id), actor="herman")
        svc.check_off(str(b_id), actor="herman")
        conn.execute("UPDATE shopping_items SET bought_at='2026-10-08 09:00:00' WHERE id=?", (a_id,))
        conn.execute("UPDATE shopping_items SET bought_at='2026-10-08 10:00:00' WHERE id=?", (b_id,))
        conn.commit()
        rows = svc.list_bought()
        self.assertEqual([r["name"] for r in rows], ["B", "A"])

    def test_clear_bought_returns_count_and_empties(self):
        svc, _ = self.make_svc()
        svc.add_items(["Milk", "Bread", "Eggs"], actor="herman")
        svc.check_off("Milk", actor="herman")
        svc.check_off("Bread", actor="herman")
        count = svc.clear_bought()
        self.assertEqual(count, 2)
        self.assertEqual([r["name"] for r in svc.list_unbought()], ["Eggs"])
        self.assertEqual(svc.clear_bought(), 0)

    def test_recent_activity_bought_first_then_added(self):
        svc, conn = self.make_svc()
        svc.add_items(["Milk", "Bread", "Eggs"], actor="herman")
        conn.execute("UPDATE shopping_items SET added_at='2026-10-08 09:00:00' WHERE name='Milk'")
        conn.execute("UPDATE shopping_items SET added_at='2026-10-08 08:00:00' WHERE name='Bread'")
        conn.execute("UPDATE shopping_items SET added_at='2026-10-08 10:00:00' WHERE name='Eggs'")
        svc.check_off("Bread", actor="herman")
        conn.execute("UPDATE shopping_items SET bought_at='2026-10-08 12:00:00' WHERE name='Bread'")
        conn.commit()
        rows = svc.recent_activity()
        # bought item first (bought_at desc), then unbought by added_at desc
        self.assertEqual([r["name"] for r in rows], ["Bread", "Eggs", "Milk"])

    def test_recent_activity_respects_limit(self):
        svc, conn = self.make_svc()
        for i in range(5):
            svc.add_items([f"Item {i}"], actor="herman")
        for i in range(5):
            conn.execute(
                "UPDATE shopping_items SET added_at=? WHERE name=?",
                (f"2026-10-08 0{i}:00:00", f"Item {i}"))
        conn.commit()
        rows = svc.recent_activity(limit=3)
        self.assertEqual(len(rows), 3)
        self.assertEqual([r["name"] for r in rows], ["Item 4", "Item 3", "Item 2"])


if __name__ == "__main__":
    unittest.main()
