from datetime import datetime, timezone

from .config import Settings
from .models import Quote, QuotesResponse
from .providers.base import Provider, ProviderError, ProviderHealth
from .validation import finalize_quote


EXPECTED_ASSETS = [
    "usd_free_irt",
    "eur_free_irt",
    "gold18_irt",
    "coin_irt",
    "gold_oz_usd",
    "silver_oz_usd",
    "tse_index",
]


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

        # Providers are ordered by preference. Invalid or stale quotes do not
        # block a later provider from supplying the same asset.
        for provider in self.providers:
            try:
                quotes = await provider.get_quotes()
            except ProviderError as exc:
                warnings.append(f"{provider.name} unavailable: {exc}")
                continue

            for quote in quotes:
                if quote.asset_id in chosen:
                    continue
                try:
                    candidate = finalize_quote(
                        quote.model_copy(deep=True),
                        now,
                        self.settings.stale_after_s,
                        self.settings.max_change_pct,
                        provider.realtime,
                        self._last_known.get(quote.asset_id),
                    )
                except ValueError as exc:
                    warnings.append(f"{quote.asset_id} rejected: {exc}")
                    continue

                if candidate.freshness.value == "stale":
                    warnings.append(
                        f"{provider.name} quote for {quote.asset_id} is stale"
                    )
                    continue

                chosen[quote.asset_id] = candidate

        final = list(chosen.values())
        for q in final:
            self._last_known[q.asset_id] = q

        # Assets we previously had but cannot supply right now.
        supplied = {q.asset_id for q in final}
        unavailable = sorted((set(self._last_known) | set(EXPECTED_ASSETS)) - supplied)
        return QuotesResponse(
            generated_at=now,
            quotes=final,
            unavailable=unavailable,
            warnings=warnings,
            stale_after_s=self.settings.stale_after_s,
        )
