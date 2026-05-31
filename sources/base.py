"""Base class for all lead-source adapters."""
from abc import ABC, abstractmethod


class Source(ABC):
    name: str = "unnamed"

    @abstractmethod
    def get_project_urls(self, limit: int) -> list[str]:
        """Return up to `limit` project page URLs."""
        ...

    @abstractmethod
    def get_page_text(self, url: str) -> str:
        """Fetch and return cleaned text for a single project URL."""
        ...
