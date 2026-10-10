import os
import sys
import tempfile
import types
import unittest

# router.py imports httpx and aiogram at module level; stub them when missing
# so this suite runs anywhere. The helpers under test are pure stdlib +
# sqlite and never touch the network or Telegram.
try:
    import httpx  # noqa: F401
except ImportError:
    sys.modules["httpx"] = types.ModuleType("httpx")

try:
    import aiogram  # noqa: F401
except ImportError:
    class _Stub:
        def __init__(self, *args, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    def _stub_module(name, **attrs):
        mod = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(mod, k, v)
        sys.modules[name] = mod

    _stub_module("aiogram", Bot=_Stub, F=_Stub(), Router=_Stub)
    _stub_module("aiogram.filters", Command=_Stub)
    _stub_module("aiogram.types", CallbackQuery=_Stub, KeyboardButton=_Stub,
                 Message=_Stub, ReplyKeyboardMarkup=_Stub)
    _stub_module("aiogram.utils")
    _stub_module("aiogram.utils.keyboard", InlineKeyboardBuilder=_Stub)

from app.db import init_db
from app.services.medicine_service import MedicineService
from app.services.shopping_service import ShoppingService
from app.bot.router import (match_medicines, symptom_matches, describe_matches,
                            parse_pick_data, format_list_contents,
                            format_open_tasks, match_template, main_keyboard,
                            fuzzy_matches)


class BotLogicTest(unittest.TestCase):
    def test_multilang_terms_dont_bury_perfect_match(self):
        """A medicine matching one term group perfectly (PL-only description)
        must not be ranked below competitors that match several translated
        variants — Tantum Verde regression."""
        conn = init_db(":memory:")
        svc = MedicineService(conn)
        svc.add({"name": "neo-angin",
                 "description_pl": "Lek w bólu gardła i stanach zapalnych jamy ustnej.",
                 "description_en": "For sore throat and mouth inflammation."})
        svc.add({"name": "Tantum Verde aerozol",
                 "description_pl": "Lek stosowany miejscowo w bólu i stanach zapalnych jamy ustnej i gardła."})
        terms = ["sore throat", "ból gardła", "zapalenie gardła", "ból w gardle"]
        rows = symptom_matches(conn, terms)
        names = [r["name"] for r in rows]
        self.assertIn("Tantum Verde aerozol", names)
        self.assertLessEqual(names.index("Tantum Verde aerozol"), 2)

class BotLogicTest(unittest.TestCase):

    def make(self, name_a="Paracetamol 500", name_b="Paracetamol kids"):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conn = init_db(os.path.join(tmp.name, "t.db"))
        svc = MedicineService(conn)
        a = svc.add({"name": name_a, "quantity": 10,
                     "description_en": "Pain and fever relief.",
                     "description_pl": "Lek na ból i gorączkę."})
        b = svc.add({"name": name_b, "quantity": 5})
        return conn, svc, a, b

    def test_match_one(self):
        conn, svc, a, b = self.make()
        self.assertEqual([r["id"] for r in match_medicines(conn, "500")], [a])

    def test_match_two_ambiguous(self):
        conn, svc, a, b = self.make()
        self.assertEqual(len(match_medicines(conn, "paracetamol")), 2)

    def test_symptom_pl(self):
        conn, svc, a, b = self.make()
        self.assertEqual([r["id"] for r in symptom_matches(conn, ["headache"])], [a])

    def test_symptom_word_parts(self):
        conn, svc, a, b = self.make()
        c = svc.add({"name": "Chemplek spray", "quantity": 1,
                     "description_pl": "Lek stosowany miejscowo w bólu i stanach "
                                       "zapalnych jamy ustnej i gardła."})
        rows = symptom_matches(conn, ["ból gardła"])
        self.assertIn(c, [r["id"] for r in rows])
        # A word-part match also fires: "stan" matches "stanach".
        rows = symptom_matches(conn, ["stan zapalny gardła"])
        self.assertEqual(rows[0]["id"], c)

    def test_symptom_weighted_cabinet(self):
        """Replica of a real user's cabinet: short generic tokens ("ból",
        "stan") must not pull in unrelated medicines."""
        conn, svc, _, _ = self.make()
        med1 = svc.add({"name": "Tantum Verde aerozol", "quantity": 1,
                        "description_pl": "Lek stosowany miejscowo w bólu i "
                                          "stanach zapalnych jamy ustnej i gardła."})
        med2 = svc.add({"name": "neo-angin", "quantity": 1,
                        "description_pl": "Lek w bólu gardła i stanach "
                                          "zapalnych jamy ustnej."})
        med3 = svc.add({"name": "Maść ichtiolowa", "quantity": 1,
                        "description_pl": "Stosowana w stanach zapalnych skóry."})
        med4 = svc.add({"name": "Tobradex", "quantity": 1,
                        "description_en": "Eye drops for eye inflammation."})
        med5 = svc.add({"name": "Paracetamol", "quantity": 1,
                        "description_en": "Pain relief."})
        rows = [r["id"] for r in symptom_matches(conn, ["ból gardła"])]
        self.assertEqual(rows, [med1, med2])
        self.assertNotIn(med3, rows)   # throat token missing -> below 60 %
        self.assertNotIn(med4, rows)
        self.assertNotIn(med5, rows)   # only short generic tokens would hit
        rows = [r["id"] for r in symptom_matches(conn, ["stan zapalny gardła"])]
        self.assertEqual(rows, [med1, med2, med3])  # med1/med2 ratio 1.0 first
        self.assertNotIn(med4, rows)
        self.assertNotIn(med5, rows)
        # limit param caps the result count.
        self.assertEqual(len(symptom_matches(conn, ["stan zapalny gardła"],
                                             limit=2)), 2)
        # Single-string signature still accepted.
        self.assertEqual([r["id"] for r in symptom_matches(conn, "ból gardła")],
                         [med1, med2])

    def test_symptom_no_match(self):
        conn, svc, a, b = self.make()
        self.assertEqual(symptom_matches(conn, ["totally unrelated xyz"]), [])

    def test_symptom_multi_term_union(self):
        conn, svc, a, b = self.make()
        c = svc.add({"name": "Chemplek spray", "quantity": 1,
                     "description_pl": "Lek stosowany miejscowo w bólu i stanach "
                                       "zapalnych jamy ustnej i gardła."})
        rows = symptom_matches(conn, ["stan zapalny gardła", "fever"])
        self.assertEqual({r["id"] for r in rows}, {a, c})
        # Best-scoring row first: three tokens hit the spray, one the tablet.
        self.assertEqual(rows[0]["id"], c)

    def test_describe(self):
        conn, svc, a, b = self.make()
        rows = match_medicines(conn, "paracetamol")
        s = describe_matches(rows, "en")
        self.assertIn("Paracetamol 500", s)
        self.assertIn("10 pieces", s)

    def test_parse_pick_data(self):
        self.assertEqual(parse_pick_data("pick:12:1"), (12, 1.0))
        self.assertEqual(parse_pick_data("pick:7:2.5"), (7, 2.5))
        self.assertEqual(parse_pick_data("pick:9"), (9, 1.0))

    def test_format_list_contents(self):
        conn = init_db(os.path.join(self.tmpdir(), "shop.db"))
        svc = ShoppingService(conn)
        svc.add_items(["milk", "bread"], "Tester")
        rows = svc.list_unbought()
        self.assertEqual(format_list_contents(rows, "en"),
                         "Shopping list:\n• milk\n• bread")

    def test_format_list_contents_empty(self):
        self.assertEqual(format_list_contents([], "en"), "")

    def test_format_open_tasks_overdue(self):
        rows = [{"title": "pay bills", "due_date": "2026-10-01",
                 "assignee_name": "Anna"}]
        self.assertEqual(format_open_tasks(rows, "en", "2026-10-08"),
                         "Open tasks:\n• OVERDUE pay bills — due 2026-10-01 → Anna")

    def test_format_open_tasks_due_today(self):
        rows = [{"title": "water plants", "due_date": "2026-10-08",
                 "assignee_name": "Anna"}]
        self.assertEqual(format_open_tasks(rows, "en", "2026-10-08"),
                         "Open tasks:\n• water plants — due 2026-10-08 → Anna")

    def test_format_open_tasks_no_due(self):
        rows = [{"title": "tidy up", "due_date": None, "assignee_name": "Anna"}]
        self.assertEqual(format_open_tasks(rows, "en", "2026-10-08"),
                         "Open tasks:\n• tidy up → Anna")

    def test_format_open_tasks_no_assignee(self):
        rows = [{"title": "buy salt", "due_date": "2026-10-08", "assignee_name": None}]
        self.assertEqual(format_open_tasks(rows, "en", "2026-10-08"),
                         "Open tasks:\n• buy salt — due 2026-10-08")

    def test_format_open_tasks_empty(self):
        self.assertEqual(format_open_tasks([], "en", "2026-10-08"), "")

    def test_match_template_en(self):
        self.assertEqual(match_template("🛒 Shopping list", "en"), "showlist")
        self.assertEqual(match_template("☑ Tasks", "en"), "showtasks")
        self.assertEqual(match_template("⏰ Expiring soon?", "en"), "expiring")
        self.assertEqual(match_template("🌐 Language", "en"), "language")
        self.assertIsNone(match_template("took a pill", "en"))
        self.assertEqual(match_template("  🛒 Shopping list  ", "en"), "showlist")

    def test_match_template_pl(self):
        self.assertEqual(match_template("🛒 Lista zakupów", "pl"), "showlist")
        self.assertEqual(match_template("☑ Zadania", "pl"), "showtasks")
        self.assertEqual(match_template("⏰ Co się kończy?", "pl"), "expiring")
        self.assertEqual(match_template("🌐 Język", "pl"), "language")
        # Button text in one language must not match another language.
        self.assertIsNone(match_template("🛒 Shopping list", "pl"))

    def test_match_template_help(self):
        from app.i18n import t
        self.assertEqual(match_template("❓ Help", "en"), "help")
        # The pl button text is read from the catalog, not hardcoded.
        self.assertEqual(match_template(t("pl", "kb_help"), "pl"), "help")
        # Other languages too.
        for code in ("ru", "uk"):
            self.assertEqual(match_template(t(code, "kb_help"), code), "help")
        # Help text must not collide with an unrelated message.
        self.assertIsNone(match_template("help me with paracetamol", "en"))

    def test_main_keyboard_layout(self):
        kb = main_keyboard("en")
        self.assertTrue(kb.resize_keyboard)
        self.assertTrue(kb.is_persistent)
        self.assertEqual([btn.text for row in kb.keyboard for btn in row],
                         ["🛒 Shopping list", "☑ Tasks",
                          "⏰ Expiring soon?", "🌐 Language", "❓ Help"])

    def test_kb_sent_migration(self):
        """init_db on a fresh DB must add the kb_sent column so the router's
        proactive-keyboard check works on databases created before it."""
        conn = init_db(os.path.join(self.tmpdir(), "mig.db"))
        conn.execute(
            "INSERT INTO allowed_users (telegram_id, name, role) VALUES (1, 'T', 'member')")
        conn.commit()
        row = conn.execute(
            "SELECT telegram_id, kb_sent FROM allowed_users WHERE telegram_id=1"
        ).fetchone()
        self.assertEqual(row["kb_sent"], 0)

    def test_fuzzy_matches_typo(self):
        conn, svc, a, b = self.make(
            name_a="Łosz Plastry z kwasem salicylowym na odciski")
        rows = fuzzy_matches(conn, "plaster na odcsiki")
        self.assertTrue(rows)
        self.assertEqual(rows[0]["id"], a)

    def test_fuzzy_matches_none(self):
        conn, svc, a, b = self.make()
        self.assertEqual(fuzzy_matches(conn, "completely different thing xyz"), [])

    def tmpdir(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return tmp.name


if __name__ == "__main__":
    unittest.main()
