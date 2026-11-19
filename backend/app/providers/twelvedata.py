from datetime import datetime, timezone

import httpx

from ..models import Market, Quote, Unit
from .base import Provider, ProviderError


class TwelveDataProvider(Provider):
    name = "TwelveData"
    realtime = False

    DEFAULT_SYMBOLS = (
        "AAPL,MSFT,EUR/USD,GBP/USD,AUD/USD,BTC/USD,ETH/USD"
    )

    CRYPTO = {"BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "BNB"}

    def __init__(
        self,
        api_key: str,
        symbols: str = "",
        min_interval_s: float = 60.0,
        timeout_s: float = 10.0,
        retries: int = 2,
    ):
        super().__init__(min_interval_s)
        self.api_key = api_key.strip()
        raw_symbols = symbols.strip() or self.DEFAULT_SYMBOLS
        self.symbols = list(dict.fromkeys(
            s.strip().upper() for s in raw_symbols.split(",") if s.strip()
        ))
        self.timeout_s = timeout_s
        self.retries = retries
        self.missing_assets: list[str] = []

    def _asset_info(self, symbol: str):
        clean = symbol.replace("/", "_").replace("-", "_").lower()
        base = symbol.split("/")[0]

        if "/" in symbol and base in self.CRYPTO:
            kind = "crypto"
        elif "/" in symbol:
            kind = "currency"
        else:
            kind = "stock"

        return f"{clean}_global", kind

    async def _fetch(self) -> list[Quote]:
        if not self.api_key:
            raise ProviderError("Twelve Data API key is not configured")

        quotes = []
        self.missing_assets = []

        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            for symbol in self.symbols:
                asset_id, kind = self._asset_info(symbol)
                data = None

                for attempt in range(self.retries + 1):
                    try:
                        response = await client.get(
                            "https://api.twelvedata.com/price",
                            params={
                                "symbol": symbol,
                                "apikey": self.api_key,
                            },
                        )

                        if response.status_code == 429:
                            raise ProviderError(
                                "Twelve Data rate limit reached"
                            )

                        response.raise_for_status()
                        payload = response.json()

                        if isinstance(payload, dict) and payload.get("status") == "error":
                            message = str(payload.get("message", "API error"))
                            if "limit" in message.lower() or payload.get("code") == 429:
                                raise ProviderError(
                                    "Twelve Data rate limit reached"
                                )
                            raise ProviderError(
                                f"Twelve Data rejected {symbol}: {message[:120]}"
                            )

                        if not isinstance(payload, dict) or payload.get("price") is None:
                            raise ValueError("price missing from response")

                        price = float(payload["price"])
                        if price <= 0:
                            raise ValueError("invalid price")

                        data = price
                        break

                    except ProviderError as exc:
                        if "rate limit" in str(exc).lower():
                            raise
                        # A symbol-specific rejection must not stop other symbols.
                        break
                    except (httpx.HTTPError, ValueError, TypeError):
                        if attempt == self.retries:
                            break

                if data is None:
                    self.missing_assets.append(asset_id)
                    continue

                quotes.append(Quote(
                    asset_id=asset_id,
                    kind=kind,
                    market=Market.GLOBAL,
                    unit=Unit.USD,
                    price=data,
                    source=self.name,
                    fetched_at=datetime.now(timezone.utc),
                ))

        if not quotes:
            raise ProviderError("Twelve Data returned no usable prices")

        return quotes
