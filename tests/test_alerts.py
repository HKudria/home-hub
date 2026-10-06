import tempfile
import unittest

from app.db import init_db
from app.services.medicine_service import MedicineService
from app.services.alerts import evaluate


class AlertTest(unittest.TestCase):
    def setup_med(self, **fields):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conn = init_db(f"{tmp.name}/t.db")
        self.addCleanup(conn.close)
        svc = MedicineService(conn)
        # Default to a stocked medicine so expiry/opened tests are not
        # contaminated by a low_stock_last alert (schema defaults are
        # quantity=0, low_stock_threshold=3). Stock tests pass quantity
        # explicitly, which overrides this default.
        fields.setdefault("quantity", 100)
        mid = svc.add({"name": "M", **fields})
        return conn, svc, mid

    def test_expiry_7_days(self):
        conn, svc, mid = self.setup_med(expiry_date="2026-10-13")
        alerts = evaluate(conn, "2026-10-06")
        self.assertEqual([a.kind for a in alerts], ["expiry_soon"])
        self.assertEqual(alerts[0].days, 7)

    def test_expiry_day(self):
        conn, svc, mid = self.setup_med(expiry_date="2026-10-06")
        self.assertEqual([a.kind for a in evaluate(conn, "2026-10-06")], ["expiry_today"])

    def test_expired_monthly(self):
        conn, svc, mid = self.setup_med(expiry_date="2026-09-06")
        self.assertEqual([a.kind for a in evaluate(conn, "2026-10-06")], ["expired"])
        self.assertEqual(evaluate(conn, "2026-10-07"), [])  # not on a 30-day boundary

    def test_expiry_snooze(self):
        # Expiry heads-up on 2026-09-29 snoozed until 2026-10-05.
        # Suppressed through the snooze end date (inclusive); re-fires as
        # expiry_today on the expiry date itself, per spec "snoozed alerts
        # re-fire after the snooze period".
        conn, svc, mid = self.setup_med(expiry_date="2026-10-06")
        conn.execute("UPDATE medicines SET snooze_expiry_until='2026-10-05' WHERE id=?",
                     (mid,))
        conn.commit()
        self.assertEqual(evaluate(conn, "2026-10-05"), [])
        self.assertEqual([a.kind for a in evaluate(conn, "2026-10-06")], ["expiry_today"])

    def test_opened_one_day_before_and_day(self):
        conn, svc, mid = self.setup_med(opened_at="2026-09-06", discard_after_days=30)
        self.assertEqual([a.kind for a in evaluate(conn, "2026-10-05")], ["opened_soon"])
        self.assertEqual([a.kind for a in evaluate(conn, "2026-10-06")], ["opened_today"])

    def test_low_stock_once_until_restock(self):
        conn, svc, mid = self.setup_med(quantity=3, low_stock_threshold=3)
        self.assertEqual([a.kind for a in evaluate(conn, "2026-10-06")], ["low_stock"])
        conn.execute("UPDATE medicines SET low_stock_notified=1 WHERE id=?", (mid,))
        conn.commit()
        self.assertEqual(evaluate(conn, "2026-10-06"), [])

    def test_snooze_past_expiry_refires_once(self):
        # Snooze extends past the expiry date: suppressed while snoozed,
        # re-fires once as "expired" on the first day after the snooze ends.
        conn, svc, mid = self.setup_med(expiry_date="2026-10-06",
                                        snooze_expiry_until="2026-11-06")
        self.assertEqual(evaluate(conn, "2026-11-05"), [])   # still snoozed
        kinds = [a.kind for a in evaluate(conn, "2026-11-07")]  # day after snooze end
        self.assertEqual(kinds, ["expired"])
        self.assertEqual(evaluate(conn, "2026-11-08"), [])   # fires only once

    def test_snooze_past_discard_refires_once(self):
        # Same re-fire guarantee for opened-after alerts, which have no
        # monthly fallback: snooze ends 2026-10-10, discard date was
        # 2026-10-06, so it fires once on 2026-10-11 as "opened_today".
        conn, svc, mid = self.setup_med(opened_at="2026-09-06", discard_after_days=30,
                                        snooze_opened_until="2026-10-10")
        self.assertEqual(evaluate(conn, "2026-10-10"), [])
        kinds = [a.kind for a in evaluate(conn, "2026-10-11")]
        self.assertEqual(kinds, ["opened_today"])
        self.assertEqual(evaluate(conn, "2026-10-12"), [])

    def test_threshold_zero_disables_stock_alerts(self):
        conn, svc, mid = self.setup_med(quantity=0, low_stock_threshold=0)
        self.assertEqual(evaluate(conn, "2026-10-06"), [])

    def test_last_dose(self):
        conn, svc, mid = self.setup_med(quantity=0, low_stock_threshold=3)
        self.assertEqual([a.kind for a in evaluate(conn, "2026-10-06")], ["low_stock_last"])


if __name__ == "__main__":
    unittest.main()
