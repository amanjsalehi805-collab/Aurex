import pytest

from app.providers.base import ProviderError
from app.providers.twelvedata import TwelveDataProvider
from app.providers.alphavantage import AlphaVantageProvider


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            request = httpx.Request("GET", "https://example.com")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                "HTTP error", request=request, response=response
            )


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, *args, **kwargs):
        return next(self.responses)


@pytest.mark.asyncio
async def test_twelvedata_keeps_valid_symbols_when_one_is_rejected(monkeypatch):
    responses = [
        FakeResponse({"price": "123.45"}),
        FakeResponse({"status": "error", "message": "Invalid symbol"}),
    ]
    monkeypatch.setattr(
        "app.providers.twelvedata.httpx.AsyncClient",
        lambda **kwargs: FakeClient(responses),
    )

    provider = TwelveDataProvider(
        api_key="test-key",
        symbols="AAPL,INVALID",
        retries=0,
    )
    quotes = await provider._fetch()

    assert len(quotes) == 1
    assert quotes[0].asset_id == "aapl_global"
    assert quotes[0].price == 123.45
    assert provider.missing_assets == ["invalid_global"]


@pytest.mark.asyncio
async def test_twelvedata_stops_on_rate_limit(monkeypatch):
    monkeypatch.setattr(
        "app.providers.twelvedata.httpx.AsyncClient",
        lambda **kwargs: FakeClient([FakeResponse({}, status_code=429)]),
    )

    provider = TwelveDataProvider(
        api_key="test-key",
        symbols="AAPL",
        retries=0,
    )

    with pytest.raises(ProviderError, match="rate limit"):
        await provider._fetch()


@pytest.mark.asyncio
async def test_alphavantage_keeps_valid_metal_when_other_is_missing(monkeypatch):
    responses = [
        FakeResponse({"price": "2650.50"}),
        FakeResponse({"Information": "Invalid symbol"}),
    ]
    monkeypatch.setattr(
        "app.providers.alphavantage.httpx.AsyncClient",
        lambda **kwargs: FakeClient(responses),
    )

    provider = AlphaVantageProvider(api_key="test-key")
    quotes = await provider._fetch()

    assert len(quotes) == 1
    assert quotes[0].asset_id == "gold_spot_usd"
    assert quotes[0].price == 2650.50
    assert provider.missing_assets == ["silver_spot_usd"]


@pytest.mark.asyncio
async def test_alphavantage_rejects_api_quota_message(monkeypatch):
    responses = [
        FakeResponse({"Note": "API call frequency limit reached"}),
    ]
    monkeypatch.setattr(
        "app.providers.alphavantage.httpx.AsyncClient",
        lambda **kwargs: FakeClient(responses),
    )

    provider = AlphaVantageProvider(api_key="test-key")

    with pytest.raises(ProviderError, match="Alpha Vantage response"):
        await provider._fetch()
