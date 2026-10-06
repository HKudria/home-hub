import os
import unittest
from unittest.mock import patch

from app.config import load_settings

# All env vars read by load_settings, so defaults are asserted hermetically.
ALL_SETTINGS_KEYS = [
    "ZAI_API_KEY",
    "ZAI_BASE_URL",
    "ZAI_VISION_MODEL",
    "ZAI_TEXT_MODEL",
    "TELEGRAM_BOT_TOKEN",
    "ADMIN_TELEGRAM_ID",
    "DAILY_CHECK_HOUR",
    "WEB_PASSWORD",
    "DATA_DIR",
    "BACKUP_KEEP_DAYS",
]


class TestLoadSettings(unittest.TestCase):
    def test_load_settings_defaults(self):
        env = {k: v for k, v in os.environ.items() if k not in ALL_SETTINGS_KEYS}
        env["ZAI_API_KEY"] = "k1"
        env["TELEGRAM_BOT_TOKEN"] = "t1"
        env["ADMIN_TELEGRAM_ID"] = "42"
        with patch.dict(os.environ, env, clear=True):
            s = load_settings()
        self.assertEqual(s.zai_api_key, "k1")
        self.assertEqual(s.admin_telegram_id, 42)
        self.assertEqual(s.daily_check_hour, 9)
        self.assertEqual(s.data_dir, "./data")
        self.assertEqual(s.backup_keep_days, 14)
        self.assertEqual(s.web_password, "")


if __name__ == "__main__":
    unittest.main()
