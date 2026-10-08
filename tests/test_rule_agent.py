import sys
import types
import unittest

# The rule agent is pure stdlib, but its Intent import transitively pulls
# app.ai.interpret which imports httpx at module level. Stub it so this
# suite runs anywhere; parse_rule_intent itself never touches the network.
try:
    import httpx  # noqa: F401
except ImportError:
    sys.modules["httpx"] = types.ModuleType("httpx")

from app.bot.rule_agent import parse_rule_intent


class RuleAgentTest(unittest.TestCase):

    def test_take_en_amount(self):
        intent = parse_rule_intent("took 2 paracetamol")
        self.assertEqual(intent.action, "take")
        self.assertEqual(intent.amount, 2)
        self.assertEqual(intent.medicine_query, "paracetamol")

    def test_take_pl(self):
        intent = parse_rule_intent("wziąłem ibuprofen")
        self.assertEqual(intent.action, "take")
        self.assertEqual(intent.amount, 1)
        self.assertEqual(intent.medicine_query, "ibuprofen")

    def test_take_ru(self):
        intent = parse_rule_intent("принял парацетамол")
        self.assertEqual(intent.action, "take")
        self.assertEqual(intent.medicine_query, "парацетамол")

    def test_take_amount_verbatim_case(self):
        intent = parse_rule_intent("wziąłem Жваліндекст.")
        self.assertEqual(intent.action, "take")
        self.assertEqual(intent.medicine_query, "Жваліндекст")

    def test_opened(self):
        self.assertEqual(parse_rule_intent("opened syrup").action, "opened")
        self.assertEqual(parse_rule_intent("открыл сироп").action, "opened")
        self.assertEqual(parse_rule_intent("відкрив сироп").action, "opened")

    def test_bought_en(self):
        intent = parse_rule_intent("bought milk")
        self.assertEqual(intent.action, "bought")
        self.assertEqual(intent.medicine_query, "milk")

    def test_bought_ru(self):
        intent = parse_rule_intent("купила хлеб")
        self.assertEqual(intent.action, "bought")
        self.assertEqual(intent.medicine_query, "хлеб")

    def test_addlist_en_commas(self):
        intent = parse_rule_intent("add mleko, chleb")
        self.assertEqual(intent.action, "addlist")
        self.assertEqual(intent.items, ["mleko", "chleb"])

    def test_addlist_uk_i_verbatim(self):
        intent = parse_rule_intent("додай хліб і Молоко")
        self.assertEqual(intent.action, "addlist")
        self.assertEqual(intent.items, ["хліб", "Молоко"])

    def test_showlist_en(self):
        self.assertEqual(parse_rule_intent("show shopping list").action,
                         "showlist")

    def test_showlist_ru(self):
        self.assertEqual(parse_rule_intent("список покупок").action,
                         "showlist")

    def test_showlist_pl(self):
        self.assertEqual(parse_rule_intent("lista zakupów").action,
                         "showlist")

    def test_showtasks_en(self):
        self.assertEqual(parse_rule_intent("show tasks").action, "showtasks")

    def test_showtasks_pl(self):
        self.assertEqual(parse_rule_intent("pokaż zadania").action,
                         "showtasks")

    def test_query_qty_pl(self):
        intent = parse_rule_intent("ile paracetamolu?")
        self.assertEqual(intent.action, "query_qty")
        self.assertEqual(intent.medicine_query, "paracetamolu")

    def test_query_qty_ru(self):
        intent = parse_rule_intent("сколько парацетамола")
        self.assertEqual(intent.action, "query_qty")
        self.assertEqual(intent.medicine_query, "парацетамола")

    def test_query_qty_en_of(self):
        intent = parse_rule_intent("how much of ibuprofen?")
        self.assertEqual(intent.action, "query_qty")
        self.assertEqual(intent.medicine_query, "ibuprofen")

    def test_expiring(self):
        self.assertEqual(parse_rule_intent("ważność leków?").action,
                         "expiring")
        self.assertEqual(parse_rule_intent("что истекает?").action,
                         "expiring")

    def test_symptom_returns_none(self):
        self.assertIsNone(parse_rule_intent("I have a headache"))
        self.assertIsNone(parse_rule_intent("boli głowa, co jest?"))

    def test_greeting_returns_none(self):
        self.assertIsNone(parse_rule_intent("hello"))

    def test_ambiguous_returns_none(self):
        self.assertIsNone(parse_rule_intent("add task pay bills on friday"))

    def test_empty_returns_none(self):
        self.assertIsNone(parse_rule_intent(""))


if __name__ == "__main__":
    unittest.main()
