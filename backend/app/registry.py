from datetime import datetime, timezone

from .config import Settings
from .models import Quote, QuotesResponse
from .providers.base import Provider, ProviderError, ProviderHealth
from .validation import finalize_quote


class Registry:
    """Providers in priority order. A lower-priority provider only fills an asset_id
    the higher ones could not supply; asset_id equality means identical market+unit."""

    def __init__(self, providers: list[Provider], settings: Settings):
        self.providers = providers
        self.settings = settings
        self._last_known: dict[str, Quote] = {}

    def health(self) -> list[ProviderHealth]:
        return [p.health for p in self.providers]

    async def quotes(self) -> QuotesResponse:
        now = datetime.now(timezone.utc)
        chosen: dict[str, Quote] = {}
        warnings: list[str] = []
        realtime_by_source: dict[str, bool] = {}

        for p in self.providers:
            realtime_by_source[p.name] = p.realtime
            try:
                quotes = await p.get_quotes()
            except ProviderError as e:
                warnings.append(f"{p.name} unavailable: {e}")
                continue
            for q in quotes:
                chosen.setdefault(q.asset_id, q.model_copy(deep=True))

        final: list[Quote] = []
        for asset_id, q in chosen.items():
            try:
                final.append(finalize_quote(
                    q, now, self.settings.stale_after_s, self.settings.max_change_pct,
                    realtime_by_source.get(q.source, False), self._last_known.get(asset_id)))
            except ValueError as e:
                warnings.append(f"{asset_id} rejected: {e}")
        for q in final:
            self._last_known[q.asset_id] = q

        # Assets we previously had but cannot supply right now.
        unavailable = sorted(set(self._last_known) - {q.asset_id for q in final})
        return QuotesResponse(generated_at=now, quotes=final,
                              unavailable=unavailable, warnings=warnings)
