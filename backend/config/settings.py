from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Idealista Official API (not yet available — set when key is received)
    # Request access at https://developers.idealista.com/
    # When obtained, set these env vars and switch IdealstaScraper → IdealstaApiClient
    IDEALISTA_API_KEY: str = ""
    IDEALISTA_API_SECRET: str = ""

    # Set to true to use your real Chrome profile when scraping Idealista.
    # Chrome must be fully closed before running the scraper.
    IDEALISTA_USE_PROFILE: bool = False

    # App
    CACHE_TTL_SECONDS: int = 1800  # 30 minutes
    SQLITE_DB_PATH: str = "cache.db"
    CORS_ORIGINS: list[str] = ["http://localhost:4200"]

    # Scraping defaults
    DEFAULT_COUNTRY: str = "es"
    REQUEST_TIMEOUT: int = 20
    MAX_PAGES: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
