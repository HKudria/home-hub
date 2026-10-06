import unittest

from app.i18n import t, detect_lang, LANGS


class TestI18n(unittest.TestCase):
    def test_langs(self):
        self.assertEqual(LANGS, ("en", "pl", "ru", "uk"))

    def test_fallback_to_en(self):
        self.assertEqual(t("xx", "app_name"), t("en", "app_name"))

    def test_missing_key_returns_key(self):
        self.assertEqual(t("en", "definitely_not_a_key"), "definitely_not_a_key")

    def test_formatting(self):
        self.assertEqual(t("en", "expires_in_days", name="A", days=7), "A expires in 7 days")

    def test_detect(self):
        self.assertEqual(detect_lang("wziąłem paracetamol"), "pl")
        self.assertIn(detect_lang("я взяв парацетамол"), ("ru", "uk"))
        self.assertEqual(detect_lang("я приняв"), "ru")
        self.assertEqual(detect_lang("узяв"), "uk")
        self.assertEqual(detect_lang("took a pill"), "en")


if __name__ == "__main__":
    unittest.main()
