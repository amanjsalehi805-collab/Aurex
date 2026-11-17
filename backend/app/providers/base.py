import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from ..models import Quote


class ProviderError(Exception):
    pass


@dataclass
class ProviderHealth:
    name: str
    status: str = "unknown"   # unknown | ok | degraded | down | unmapped
    last_success: datetime | None = None
    last_error: str | None = None
    consecutive_failures: int = 0


class Provider(ABC):
    """Base class: rate gating, health tracking. Subclasses implement _fetch()."""

    name: str = "provider"
    realtime: bool = False  # only True if the provider documents real-time data

    def __init__(self, min_interval_s: float):
        self.min_interval_s = min_interval_s
        self.health = ProviderHealth(name=self.name)
        self._last_attempt: float | None = None
        self._last_result: list[Quote] | None = None

    async def get_quotes(self) -> list[Quote]:
        now = time.monotonic()
        if self._last_attempt is not None and now - self._last_attempt < self.min_interval_s:
            if self._last_result is not None:
                return self._last_result
            raise ProviderError(self.health.last_error or "rate gate active")
        self._last_attempt = now
        try:
            quotes = await self._fetch()
        except ProviderError as e:
            self._record_failure(str(e))
            raise
        except Exception as e:  # network, parsing, etc.
            self._record_failure(f"{type(e).__name__}: {e}")
            raise ProviderError(str(e)) from e
        self._last_result = quotes
        self.health.status = "ok"
        self.health.last_success = datetime.now(timezone.utc)
        self.health.last_error = None
        self.health.consecutive_failures = 0
        return quotes

    def _record_failure(self, msg: str) -> None:
        self.health.consecutive_failures += 1
        self.health.last_error = msg
        if self.health.status != "unmapped":
            self.health.status = "down" if self.health.consecutive_failures >= 3 else "degraded"

    @abstractmethod
    async def _fetch(self) -> list[Quote]: ...
