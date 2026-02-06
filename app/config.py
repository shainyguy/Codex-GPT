from dataclasses import dataclass
import os


@dataclass(slots=True)
class Settings:
    bot_token: str
    public_base_url: str
    database_path: str
    poll_interval_seconds: int
    yookassa_shop_id: str
    yookassa_secret_key: str
    yookassa_return_url: str
    gigachat_api_key: str
    gigachat_model: str
    gigachat_base_url: str



def load_settings() -> Settings:
    return Settings(
        bot_token=os.getenv("BOT_TOKEN", ""),
        public_base_url=os.getenv("PUBLIC_BASE_URL", "http://localhost:8000"),
        database_path=os.getenv("DATABASE_PATH", "radar.db"),
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "20")),
        yookassa_shop_id=os.getenv("YOOKASSA_SHOP_ID", ""),
        yookassa_secret_key=os.getenv("YOOKASSA_SECRET_KEY", ""),
        yookassa_return_url=os.getenv("YOOKASSA_RETURN_URL", "https://t.me"),
        gigachat_api_key=os.getenv("GIGACHAT_API_KEY", ""),
        gigachat_model=os.getenv("GIGACHAT_MODEL", "GigaChat"),
        gigachat_base_url=os.getenv(
            "GIGACHAT_BASE_URL", "https://gigachat.devices.sberbank.ru/api/v1"
        ),
    )
