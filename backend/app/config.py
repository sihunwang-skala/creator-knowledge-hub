"""Runtime configuration. All secrets come from environment variables (prefix CKH_)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CKH_", extra="ignore")

    database_url: str = "sqlite:///./data/ckh.db"
    youtube_api_key: str = ""
    youtube_daily_quota: int = 10_000
    youtube_search_daily_limit: int = 100  # search.list has its own bucket
    metadata_max_age_days: int = 30  # YouTube API policy: refresh/delete stored API data
    enable_stat_filters: bool = False  # view/subscriber filters: policy review pending
    llm_provider: str = "local"  # local | anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    llm_daily_call_limit: int = 50
    search_provider: str = "fixture"  # fixture | brave
    brave_api_key: str = ""
    allow_signup: bool = True
    enable_scheduler: bool = False
    max_upload_bytes: int = 1_000_000
    max_segments: int = 20_000
    rate_limit_per_minute: int = 120
    expensive_rate_limit_per_minute: int = 20
    allow_web_fetch: bool = True
    web_fetch_max_bytes: int = 500_000

    @property
    def demo_mode(self) -> bool:
        return not self.youtube_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
