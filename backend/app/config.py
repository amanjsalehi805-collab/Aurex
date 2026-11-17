from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    aurex_env: str = "prod"
    talasanj_api_key: str = ""
    talasanj_base_url: str = "https://talasanj.info/api/v1"
    talasanj_min_interval_s: float = 60.0
    http_timeout_s: float = 10.0
    http_retries: int = 2
    stale_after_s: int = 900
    max_change_pct: float = 15.0
    client_rate_limit_per_min: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
