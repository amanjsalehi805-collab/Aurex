from datetime import datetime, timezone
import httpx

from ..models import Market, Quote, Unit
from .base import Provider, ProviderError


class NerkhAraProvider(Provider):
    name = "NerkhAra"
    realtime = False

    ASSETS = {
        "usd": ("usd_free_irt", "currency", Market.FREE, Unit.IRT),
        "eur": ("eur_free_irt", "currency", Market.FREE, Unit.IRT),
        "xau": ("gold_oz_usd", "gold", Market.GLOBAL, Unit.USD),
        "xag": ("silver_oz_usd", "metal", Market.GLOBAL, Unit.USD),
    }

    def __init__(
        self,
        base_url: str,
        min_interval_s: float,
        timeout_s: float,
        stale_after_s: int,
    ):
        super().__init__(min_interval_s)
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.stale_after_s = stale_after_s

    async def _fetch(self) -> list[Quote]:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; AUREX/0.2)",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_s,
                headers=headers,
                follow_redirects=True,
            ) as client:
                response = await client.get(f"{self.base_url}/latest.json")
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(
                f"NerkhAra request failed: {type(exc).__name__}"
            ) from exc

        if not isinstance(payload, dict) or payload.get("stale") is True:
            raise ProviderError("NerkhAra dataset is stale or invalid")

        items = payload.get("items")
        if not isinstance(items, list):
            raise ProviderError("NerkhAra response has no valid items list")

        now = datetime.now(timezone.utc)
        by_id = {
            item.get("id"): item
            for item in items
            if isinstance(item, dict) and item.get("id")
        }

        quotes = []
        for source_id, spec in self.ASSETS.items():
            item = by_id.get(source_id)
            if not item or item.get("stale") is True:
                continue

            try:
                price = float(item["price"])
                if not (price > 0 and price < float("inf")):
                    continue

                if str(item.get("unit", "")).upper() != spec[3].value:
                    continue

                raw_ts = item.get("updated_utc")
                if not isinstance(raw_ts, str):
                    continue

                source_ts = datetime.fromisoformat(
                    raw_ts.replace("Z", "+00:00")
                )
                if source_ts.tzinfo is None:
                    source_ts = source_ts.replace(tzinfo=timezone.utc)

                age = (now - source_ts).total_seconds()
                if age < -300 or age > self.stale_after_s:
                    continue

                change_pct = item.get("change_pct")
                if change_pct is not None:
                    change_pct = float(change_pct)
                    if not (-100 < change_pct < 1000):
                        change_pct = None

                quotes.append(
                    Quote(
                        asset_id=spec[0],
                        kind=spec[1],
                        market=spec[2],
                        unit=spec[3],
                        price=price,
                        change_pct=change_pct,
                        source=self.name,
                        source_timestamp=source_ts,
                        fetched_at=now,
                    )
                )
            except (KeyError, TypeError, ValueError, OverflowError):
                continue

        if not quotes:
            raise ProviderError("NerkhAra returned no fresh supported quotes")

        return quotes
