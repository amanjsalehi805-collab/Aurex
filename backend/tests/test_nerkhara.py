from datetime import datetime, timedelta, timezone

import pytest

from app.config import Settings
from app.models import Market, Quote, Unit
from app.providers.base import Provider, ProviderError
from app.providers.nerkhara import NerkhAraProvider
from app.registry import Registry


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        pass


class FakeClient:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, *args, **kwargs):
        return self.response


@pytest.mark.asyncio
async def test_nerkhara_maps_fresh_assets_and_skips_stale(monkeypatch):
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(minutes=2)).isoformat()

    payload = {
        "stale": False,
        "items": [
            {"id": "usd", "price": 270000, "unit": "IRT",
             "updated_utc": recent, "stale": False},
            {"id": "eur", "price": 296000, "unit": "IRT",
             "updated_utc": recent, "stale": False},
            {"id": "xau", "price": 3600, "unit": "USD",
             "updated_utc": recent, "stale": False},
            {"id": "xag", "price": 42, "unit": "USD",
             "updated_utc": recent, "stale": True},
        ],
    }

    monkeypatch.setattr(
        "app.providers.nerkhara.httpx.AsyncClient",
        lambda **kwargs: FakeClient(FakeResponse(payload)),
    )

    provider = NerkhAraProvider(
        "https://example.com/api/v1", 600, 10, 900
    )
    quotes = await provider._fetch()

    assert {q.asset_id for q in quotes} == {
        "usd_free_irt", "eur_free_irt", "gold_oz_usd"
    }
    assert all(q.source == "NerkhAra" for q in quotes)


@pytest.mark.asyncio
async def test_nerkhara_rejects_old_dataset(monkeypatch):
    old = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    payload = {
        "stale": False,
        "items": [
            {"id": "usd", "price": 270000, "unit": "IRT",
             "updated_utc": old, "stale": False},
        ],
    }

    monkeypatch.setattr(
        "app.providers.nerkhara.httpx.AsyncClient",
        lambda **kwargs: FakeClient(FakeResponse(payload)),
    )

    provider = NerkhAraProvider(
        "https://example.com/api/v1", 600, 10, 900
    )

    with pytest.raises(Exception, match="no fresh supported quotes"):
        await provider._fetch()


@pytest.mark.asyncio
async def test_nerkhara_reports_http_status(monkeypatch):
    import httpx

    class ErrorResponse:
        def raise_for_status(self):
            request = httpx.Request("GET", "https://example.com/latest.json")
            response = httpx.Response(503, request=request)
            raise httpx.HTTPStatusError(
                "Service unavailable", request=request, response=response
            )

    monkeypatch.setattr(
        "app.providers.nerkhara.httpx.AsyncClient",
        lambda **kwargs: FakeClient(ErrorResponse()),
    )

    provider = NerkhAraProvider("https://example.com", 600, 10, 900)

    with pytest.raises(ProviderError, match="HTTP 503"):
        await provider._fetch()


@pytest.mark.asyncio
async def test_nerkhara_rejects_invalid_json(monkeypatch):
    class InvalidJSONResponse(FakeResponse):
        def json(self):
            raise ValueError("invalid JSON")

    monkeypatch.setattr(
        "app.providers.nerkhara.httpx.AsyncClient",
        lambda **kwargs: FakeClient(InvalidJSONResponse({})),
    )

    provider = NerkhAraProvider("https://example.com", 600, 10, 900)

    with pytest.raises(ProviderError, match="invalid JSON"):
        await provider._fetch()


@pytest.mark.asyncio
async def test_nerkhara_skips_invalid_assets_and_keeps_valid_quote(monkeypatch):
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(minutes=2)).isoformat()
    future = (now + timedelta(minutes=10)).isoformat()

    payload = {
        "stale": False,
        "items": [
            {"id": "usd", "price": 270000, "unit": "IRT",
             "updated_utc": recent, "stale": False},
            {"id": "eur", "price": 0, "unit": "IRT",
             "updated_utc": recent, "stale": False},
            {"id": "xau", "price": 3600, "unit": "EUR",
             "updated_utc": recent, "stale": False},
            {"id": "xag", "price": 42, "unit": "USD",
             "updated_utc": future, "stale": False},
        ],
    }

    monkeypatch.setattr(
        "app.providers.nerkhara.httpx.AsyncClient",
        lambda **kwargs: FakeClient(FakeResponse(payload)),
    )

    provider = NerkhAraProvider("https://example.com", 600, 10, 900)
    quotes = await provider._fetch()

    assert len(quotes) == 1
    assert quotes[0].asset_id == "usd_free_irt"
    assert quotes[0].price == 270000


class StaticProvider(Provider):
    def __init__(self, name, quotes):
        super().__init__(0)
        self.name = name
        self.health.name = name
        self.quotes = quotes

    async def _fetch(self):
        return self.quotes


def make_quote(asset_id, price, source, timestamp):
    return Quote(
        asset_id=asset_id,
        kind="currency",
        market=Market.FREE,
        unit=Unit.IRT,
        price=price,
        source=source,
        source_timestamp=timestamp,
        fetched_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_registry_falls_back_when_first_provider_is_stale():
    old = datetime.now(timezone.utc) - timedelta(minutes=30)
    recent = datetime.now(timezone.utc) - timedelta(minutes=1)

    first = StaticProvider(
        "Primary", [make_quote("usd_free_irt", 260000, "Primary", old)]
    )
    second = StaticProvider(
        "Fallback", [make_quote("usd_free_irt", 270000, "Fallback", recent)]
    )

    registry = Registry(
        [first, second],
        Settings(stale_after_s=900, max_change_pct=15),
    )
    result = await registry.quotes()

    usd = next(q for q in result.quotes if q.asset_id == "usd_free_irt")
    assert usd.price == 270000
    assert usd.source == "Fallback"
    assert usd.freshness.value != "stale"
