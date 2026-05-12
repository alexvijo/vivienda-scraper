from abc import ABC, abstractmethod
from models.property import Property, SearchFilters


class BaseScraper(ABC):
    """Abstract base class for all real-estate platform scrapers."""

    platform: str = ""

    @abstractmethod
    def search(self, filters: SearchFilters) -> list[Property]:
        """Search for properties matching the given filters.

        Args:
            filters: Search parameters (city, price range, rooms, etc.)

        Returns:
            List of normalized Property objects.
        """
        ...

    def is_available(self) -> bool:
        """Return True if this scraper is ready to use (credentials set, etc.)."""
        return True
