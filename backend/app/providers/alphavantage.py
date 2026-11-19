import asyncio
from datetime import datetime, timezone

import httpx

from ..models import Market, Quote, Unit
from .base import Provider, ProviderError


class AlphaVantageProvider(Provider):
    name = "AlphaVantage"
    realtime = False

    METALS = {
        "GOLD": ("gold_spot_usd", "gold"),
        "SILVER": ("silver_spot_usd", "metal"),
    }

    def __init__(
        self,
        api_key: str,
        min_interval_s: float = 43200.0,
        timeout_s: float = 10.0,
    ):
        super().__init__(min_interval_s)
        self.api_key = api_key.strip()
        self.timeout_s = timeout_s
        self.missing_assets: list[str] = []

    async def _fetch(self) -> list[Quote]:
        if not self.api_key:
            raise ProviderError("Alpha Vantage API key is not configured")

        quotes = []
        self.missing_assets = []

        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            for index, (symbol, (asset_id, kind)) in enumerate(self.METALS.items()):
                if index:
                    await asyncio.sleep(1.1)
                try:
                    response = await client.get(
                        "https://www.alphavantage.co/query",
                        params={
                            "function": "GOLD_SILVER_SPOT",
                            "symbol": symbol,
                            "apikey": self.api_key,
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()

                    if not isinstance(payload, dict):
                        raise ValueError("invalid response")

                    api_error = (
                        payload.get("Error Message")
                        or payload.get("Information")
                        or payload.get("Note")
                    )
                    if api_error:
                        if "invalid symbol" in str(api_error).lower():
                            missing_assets.append(asset_id)
                            continue
                        raise ProviderError(
                            f"Alpha Vantage response: {str(api_error)[:160]}"
                        )

                    raw_price = payload.get("price")
                    if raw_price is None:
                        raise ValueError("price missing")

                    price = float(raw_price)
                    if price <= 0:
                        raise ValueError("invalid price")

                    timestamp = None
                    raw_timestamp = payload.get("timestamp")
                    if raw_timestamp:
                        timestamp = datetime.fromisoformat(
                            str(raw_timestamp).replace("Z", "+00:00")
                        )
                        if timestamp.tzinfo is None:
                            timestamp = timestamp.replace(tzinfo=timezone.utc)

                    quotes.append(Quote(
                        asset_id=asset_id,
                        kind=kind,
                        market=Market.GLOBAL,
                        unit=Unit.USD,
                        price=price,
                        source=self.name,
                        source_timestamp=timestamp,
                        fetched_at=datetime.now(timezone.utc),
                    ))

                except ProviderError:
                    raise
                except (httpx.HTTPError, ValueError, TypeError):
                    self.missing_assets.append(asset_id)

        if not quotes:
            raise ProviderError("Alpha Vantage returned no usable metal prices")

        return quotes
