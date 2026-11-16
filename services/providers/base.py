"""Provider interface. Every rate source (demo, manual, live) implements this."""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class RateRecord:
    key: str
    value: float


class ProviderError(Exception):
    """A fetch or parse failure. The service keeps the last good rates and backs off."""


class ProviderNotReady(ProviderError):
    """The provider is not configured or not authorised yet."""


class RateProvider(ABC):
    name = "base"
    polled = True        # True: the poller pulls rates. False: rates are pushed in (manual entry).
    min_interval = 0     # provider's permitted minimum seconds between requests

    def available(self) -> bool:
        return True

    def status_text(self) -> str:
        return "Ready"

    @abstractmethod
    def fetch(self) -> list[RateRecord]:
        """Return the latest rates, or raise ProviderError."""
