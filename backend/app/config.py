from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    aurex_env: str = "prod"
    talasanj_api_key: str = ""
    talasanj_api_key_backup: str = ""
    twelvedata_api_key: str = ""
    twelvedata_symbols: str = "AAPL,MSFT,EUR/USD,GBP/USD,AUD/USD,BTC/USD,ETH/USD"
    twelvedata_min_interval_s: float = 900.0
    alpha_vantage_api_key: str = ""
    alpha_vantage_min_interval_s: float = 43200.0
    nerkhara_base_url: str = "https://nerkhara.com/api/v1"
    nerkhara_min_interval_s: float = 60.0
    talasanj_base_url: str = "https://talasanj.info/api/v1"
    talasanj_min_interval_s: float = 60.0
    http_timeout_s: float = 10.0
    http_retries: int = 2
    stale_after_s: int = 900
    max_change_pct: float = 15.0
    client_rate_limit_per_min: int = 60


    # --- AI ---
    ai_provider: str = "openai"
    ai_api_key: str = ""
    ai_base_url: str = ""
    ai_model: str = ""
    ai_timeout_s: float = 45.0
    ai_max_output_tokens: int = 700
    ai_rate_limit_per_min: int = 10
    analysis_cache_ttl_s: int = 600

    # --- AI fallback providers ---
    ai_fallback_1_provider: str = ""
    ai_fallback_1_api_key: str = ""
    ai_fallback_1_base_url: str = ""
    ai_fallback_1_model: str = ""

    ai_fallback_2_provider: str = ""
    ai_fallback_2_api_key: str = ""
    ai_fallback_2_base_url: str = ""
    ai_fallback_2_model: str = ""

    # --- History and stocks ---
    history_db_path: str = "data/aurex.db"
    history_min_interval_s: int = 300
    history_retention_days: int = 90
    rates_collect_interval_s: int = 60
    collect_interval_s: int = 300
    admin_token: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
