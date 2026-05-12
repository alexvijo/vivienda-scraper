import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from models.property import Property, SearchFilters


class BaseScraper(ABC):
    """Abstract base class for all real-estate platform scrapers."""

    platform: str = ""

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger(f"scrapers.{self.platform}")

    @staticmethod
    def now_iso() -> datetime:
        return datetime.now(timezone.utc)

    @abstractmethod
    def search(self, filters: SearchFilters) -> list[Property]:
        ...

    def is_available(self) -> bool:
        return True
