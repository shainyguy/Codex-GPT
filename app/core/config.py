from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'AgentHub'
    environment: str = 'dev'
    base_url: str = 'http://localhost:8000'
    secret_key: str = Field(...)
    access_token_expire_minutes: int = 60 * 24
    jwt_algorithm: str = 'HS256'

    postgres_dsn: str = Field(...)
    redis_dsn: str = Field(...)

    yookassa_shop_id: str = ''
    yookassa_secret_key: str = ''

    openai_api_key: str = ''
    anthropic_api_key: str = ''
    gemini_api_key: str = ''
    mistral_api_key: str = ''
    cohere_api_key: str = ''
    deepseek_api_key: str = ''
    yandex_api_key: str = ''
    yandex_folder_id: str = ''
    gigachat_api_key: str = ''

    default_trial_days: int = 7
    free_plan_tokens: int = 30000


@lru_cache
def get_settings() -> Settings:
    return Settings()
