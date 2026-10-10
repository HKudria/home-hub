import datetime
import tempfile
import unittest

from app.db import init_db
from app.services.medicine_service import MedicineService


class MedicineServiceTest(unittest.TestCase):
    def make_svc(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conn = init_db(f"{tmp.name}/t.db")
        self.addCleanup(conn.close)
        return MedicineService(conn), conn

    def test_add_and_get(self):
        svc, _ = self.make_svc()
        mid = svc.add({"name": "Paracetamol 500", "quantity": 20, "expiry_date": "2027-01-01"})
        row = svc.get(mid)
        self.assertEqual(row["name"], "Paracetamol 500")
        self.assertEqual(row["ai_status"], "ok")

    def test_add_defaults_threshold_off(self):
        # Threshold 0 = low-stock alerts off unless the user sets one
        # (alerts.py only fires when threshold > 0).
        svc, _ = self.make_svc()
        mid = svc.add({"name": "A", "quantity": 20, "expiry_date": "2027-01-01"})
        row = svc.get(mid)
        self.assertEqual(row["low_stock_threshold"], 0)

    def test_list_all_nulls_last(self):
        svc, _ = self.make_svc()
        svc.add({"name": "NoDate"})
        svc.add({"name": "Dated", "expiry_date": "2027-05-01"})
        rows = svc.list_all()
        self.assertEqual(rows[0]["name"], "Dated")

    def test_take_dose(self):
        svc, conn = self.make_svc()
        mid = svc.add({"name": "A", "quantity": 5, "low_stock_threshold": 3})
        row = svc.take_dose(mid, 1, "herman")
        self.assertEqual(row["quantity"], 4)
        ev = conn.execute("SELECT * FROM events WHERE medicine_id=?", (mid,)).fetchone()
        self.assertEqual(ev["delta"], -1)
        self.assertEqual(ev["actor"], "herman")

    def test_take_dose_floors_at_zero(self):
        svc, _ = self.make_svc()
        mid = svc.add({"name": "A", "quantity": 1})
        row = svc.take_dose(mid, 5, "x")
        self.assertEqual(row["quantity"], 0)

    def test_take_dose_resets_low_stock_flag_when_restocked(self):
        svc, conn = self.make_svc()
        mid = svc.add({"name": "A", "quantity": 2})
        svc.take_dose(mid, 1, "x")  # low stock triggered elsewhere
        conn.execute("UPDATE medicines SET low_stock_notified=1 WHERE id=?", (mid,))
        conn.commit()
        svc.take_dose(mid, -10, "restock")  # delta negative amount => adds
        row = svc.get(mid)
        self.assertEqual(row["low_stock_notified"], 0)

    def test_mark_opened_and_discard(self):
        svc, conn = self.make_svc()
        mid = svc.add({"name": "Syrup", "discard_after_days": 30})
        svc.mark_opened(mid, "2026-10-06", "herman")
        self.assertEqual(svc.get(mid)["opened_at"], "2026-10-06")
        svc.discard(mid, "herman")
        self.assertIsNone(svc.get(mid))
        c = conn.execute(
            "SELECT COUNT(*) c FROM events WHERE medicine_id=?", (mid,)).fetchone()["c"]
        self.assertEqual(c, 0)

    def test_update_snooze_fields(self):
        svc, _ = self.make_svc()
        mid = svc.add({"name": "A", "expiry_date": "2026-10-06"})
        svc.update(mid, {"snooze_expiry_until": "2026-11-06"})
        self.assertEqual(svc.get(mid)["snooze_expiry_until"], "2026-11-06")


if __name__ == "__main__":
    unittest.main()
