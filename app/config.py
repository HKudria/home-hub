import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    zai_api_key: str
    zai_base_url: str
    zai_vision_model: str
    zai_text_model: str
    telegram_bot_token: str
    admin_telegram_id: int
    daily_check_hour: int
    web_password: str
    data_dir: str
    backup_keep_days: int


def load_settings() -> Settings:
    return Settings(
        zai_api_key=os.environ.get("ZAI_API_KEY", ""),
        zai_base_url=os.environ.get("ZAI_BASE_URL", "https://api.z.ai/api/paas/v4"),
        zai_vision_model=os.environ.get("ZAI_VISION_MODEL", "glm-4.5v"),
        zai_text_model=os.environ.get("ZAI_TEXT_MODEL", "glm-4.6"),
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        admin_telegram_id=int(os.environ.get("ADMIN_TELEGRAM_ID", "").strip() or "0"),
        daily_check_hour=int(os.environ.get("DAILY_CHECK_HOUR", "").strip() or "9"),
        web_password=os.environ.get("WEB_PASSWORD", ""),
        data_dir=os.environ.get("DATA_DIR", "./data"),
        backup_keep_days=int(os.environ.get("BACKUP_KEEP_DAYS", "").strip() or "14"),
    )
