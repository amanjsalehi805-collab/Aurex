import hashlib
import json
import asyncio
import hmac
import logging
import re
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import ai as ai_mod
from .config import get_settings
from .history import HistoryStore, summarize
from .providers.base import ProviderError
from .providers.talasanj import TalasanjProvider
from .providers.twelvedata import TwelveDataProvider
from .providers.alphavantage import AlphaVantageProvider
from .registry import Registry
from .stocks import StockService, valid_symbol

log = logging.getLogger("aurex")
VERSION = "0.2.0"
_ASSET_RE = re.compile(r"^[a-z0-9_]{1,40}$")


def _ts(quote) -> int:
    return int(quote.fetched_at.timestamp())


async def _collect(app: FastAPI):
    """Collect real quotes and record only received market data."""
    response = await app.state.registry.quotes()

    items = [
        {
            "asset_id": quote.asset_id,
            "price": quote.price,
            "unit": quote.unit.value,
            "source": quote.source,
            "ts": _ts(quote),
            "freshness": quote.freshness.value,
        }
        for quote in response.quotes
    ]

    await asyncio.to_thread(app.state.history.record, items)
    return response


async def _collector_loop(app: FastAPI, interval: int):
    while True:
        try:
            await _collect(app)
            await app.state.stocks.refresh()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("collector error: %s", type(exc).__name__)

        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    talasanj = TalasanjProvider(
        settings.talasanj_api_key,
        settings.talasanj_base_url,
        settings.talasanj_min_interval_s,
        settings.http_timeout_s,
        settings.http_retries,
        settings.talasanj_api_key_backup,
    )

    providers = [talasanj]

    if settings.twelvedata_api_key:
        twelvedata = TwelveDataProvider(
            api_key=settings.twelvedata_api_key,
            symbols=settings.twelvedata_symbols,
            min_interval_s=settings.twelvedata_min_interval_s,
            timeout_s=settings.http_timeout_s,
            retries=settings.http_retries,
        )
        providers.append(twelvedata)
        app.state.twelvedata = twelvedata

    if settings.alpha_vantage_api_key:
        alpha_vantage = AlphaVantageProvider(
            api_key=settings.alpha_vantage_api_key,
            min_interval_s=settings.alpha_vantage_min_interval_s,
            timeout_s=settings.http_timeout_s,
        )
        providers.append(alpha_vantage)
        app.state.alpha_vantage = alpha_vantage

    app.state.talasanj = talasanj
    app.state.registry = Registry(providers, settings)

    app.state.history = HistoryStore(
        settings.history_db_path,
        settings.history_min_interval_s,
        settings.history_retention_days,
    )

    app.state.stocks = StockService(
        settings.history_db_path,
        retention_days=settings.history_retention_days,
    )

    app.state.ai = ai_mod.AiService(
        settings.ai_provider,
        settings.ai_api_key,
        settings.ai_base_url,
        settings.ai_model,
        settings.ai_timeout_s,
        settings.ai_max_output_tokens,
    )

    app.state.analysis_cache = {}

    task = None
    if settings.collect_interval_s > 0:
        task = asyncio.create_task(
            _collector_loop(app, settings.collect_interval_s)
        )

    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(
    title="AUREX backend",
    version=VERSION,
    lifespan=lifespan,
)

_hits: dict[str, deque] = defaultdict(deque)
_ai_hits: dict[str, deque] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    # Use the socket peer; do not trust client-supplied forwarded headers.
    return request.client.host if request.client else "unknown"


def _limited(bucket: dict[str, deque], ip: str, limit: int) -> bool:
    now = time.monotonic()
    queue = bucket[ip]

    while queue and now - queue[0] > 60:
        queue.popleft()

    if limit <= 0 or len(queue) >= limit:
        return True

    queue.append(now)
    return False


@app.middleware("http")
async def client_rate_limit(request: Request, call_next):
    limit = get_settings().client_rate_limit_per_min

    if _limited(_hits, _client_ip(request), limit):
        return JSONResponse(
            {"detail": "rate limit exceeded"},
            status_code=429,
        )

    return await call_next(request)


def _ai_error(error: ai_mod.AiError) -> JSONResponse:
    return JSONResponse(
        {"detail": error.code, "code": error.code},
        status_code=error.status,
    )


# Core endpoints

@app.get("/health")
async def health():
    return {"status": "ok", "version": VERSION}


@app.get("/v1/providers/health")
async def providers_health():
    return [item.__dict__ for item in app.state.registry.health()]


@app.get("/v1/quotes")
async def quotes():
    return await _collect(app)


@app.get("/v1/history/{asset_id}")
async def history(asset_id: str, hours: int = 24):
    if not _ASSET_RE.fullmatch(asset_id):
        raise HTTPException(status_code=422, detail="invalid asset_id")

    if hours < 1 or hours > 24 * 90:
        raise HTTPException(
            status_code=422,
            detail="hours must be 1..2160",
        )

    since = int(time.time()) - hours * 3600

    points = await asyncio.to_thread(
        app.state.history.series,
        asset_id,
        since,
    )
    unit = await asyncio.to_thread(
        app.state.history.unit_of,
        asset_id,
    )

    return {
        "asset_id": asset_id,
        "unit": unit,
        "hours": hours,
        "points": [
            {"ts": timestamp, "price": price}
            for timestamp, price in points
        ],
        "summary": summarize(points),
        "note": "Recorded from real quotes only; no back-filled data.",
    }


# Iranian stocks infrastructure

class SymbolIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    name: str | None = Field(default=None, max_length=80)
    market: str | None = Field(default=None, max_length=80)


def _require_admin(request: Request):
    token = get_settings().admin_token

    if not token:
        raise HTTPException(
            status_code=403,
            detail="admin routes disabled",
        )

    supplied = request.headers.get("x-admin-token", "")

    if not hmac.compare_digest(
        supplied.encode(),
        token.encode(),
    ):
        raise HTTPException(status_code=403, detail="forbidden")


@app.get("/v1/stocks/status")
async def stocks_status():
    return app.state.stocks.status()


@app.get("/v1/stocks/symbols")
async def stocks_symbols():
    symbols = await asyncio.to_thread(app.state.stocks.symbols)
    return {"symbols": symbols}


@app.post("/v1/stocks/symbols")
async def stocks_add(body: SymbolIn, request: Request):
    _require_admin(request)

    try:
        created = await asyncio.to_thread(
            app.state.stocks.add_symbol,
            body.symbol,
            body.name,
            body.market,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )

    return {"created": created}


@app.delete("/v1/stocks/symbols/{symbol}")
async def stocks_remove(symbol: str, request: Request):
    _require_admin(request)

    if not valid_symbol(symbol):
        raise HTTPException(status_code=422, detail="invalid symbol")

    removed = await asyncio.to_thread(
        app.state.stocks.remove_symbol,
        symbol,
    )
    return {"removed": removed}


@app.get("/v1/stocks/quotes")
async def stocks_quotes():
    status = app.state.stocks.status()
    quotes_data = await asyncio.to_thread(app.state.stocks.quotes)

    return {
        **status,
        "quotes": quotes_data,
    }


@app.get("/v1/stocks/{symbol}/history")
async def stocks_history(symbol: str, hours: int = 24 * 7):
    if not valid_symbol(symbol) or hours < 1 or hours > 24 * 365:
        raise HTTPException(status_code=422, detail="invalid input")

    points = await asyncio.to_thread(
        app.state.stocks.history,
        symbol,
        int(time.time()) - hours * 3600,
    )

    return {
        "symbol": symbol,
        "points": [
            {"ts": timestamp, "price": price}
            for timestamp, price in points
        ],
        "summary": summarize(points),
    }


# AI assistant and market analysis

class ChatMessage(BaseModel):
    role: str
    content: str = Field(min_length=1, max_length=2000)


class ChatIn(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=20)
    language: str = "en"


class AnalysisIn(BaseModel):
    language: str = "en"
    force: bool = False


def _lang(value: str) -> str:
    return value if value in ai_mod.LANG_NAMES else "en"


async def _facts():
    response = await _collect(app)
    now = int(time.time())

    quotes_data = [
        quote.model_dump(mode="json")
        for quote in response.quotes
    ]

    stats = {}

    for quote in quotes_data:
        asset_id = quote["asset_id"]
        points = await asyncio.to_thread(
            app.state.history.series,
            asset_id,
            now - 7 * 86400,
        )
        stats[asset_id] = summarize(points)

    facts = ai_mod.build_facts(
        quotes_data,
        stats,
        response.unavailable,
    )

    return response, facts, stats, now


@app.get("/v1/ai/status")
async def ai_status():
    return app.state.ai.info()


@app.post("/v1/ai/chat")
async def ai_chat(body: ChatIn, request: Request):
    if not app.state.ai.configured:
        return _ai_error(
            ai_mod.AiError("ai_not_configured", 503)
        )

    if _limited(
        _ai_hits,
        _client_ip(request),
        get_settings().ai_rate_limit_per_min,
    ):
        return _ai_error(
            ai_mod.AiError("ai_rate_limited", 429)
        )

    try:
        messages = ai_mod.validate_messages([
            message.model_dump()
            for message in body.messages
        ])

        _, facts, _, now = await _facts()

        prompt = ai_mod.system_prompt(
            _lang(body.language),
            facts,
            now,
        )

        reply = await app.state.ai.complete(prompt, messages)

    except ai_mod.AiError as error:
        return _ai_error(error)

    return {
        "reply": reply,
        "generated_at": now,
        "model": app.state.ai.model,
        "data_quotes": len(facts["quotes"]),
    }


@app.post("/v1/ai/analysis")
async def ai_analysis(body: AnalysisIn, request: Request):
    language = _lang(body.language)

    response, facts, stats, now = await _facts()

    history_ok = any(
        item.get("sufficient")
        for item in stats.values()
    )

    base = {
        "generated_at": now,
        "language": language,
        "data": facts,
        "sources": sorted({
            quote["source"]
            for quote in facts["quotes"]
            if quote.get("source")
        }),
        "history_sufficient": history_ok,
        "warnings": response.warnings,
    }

    if not facts["quotes"]:
        return {
            **base,
            "status": "no_data",
            "ai": {"status": "no_data", "text": None},
        }

    if not app.state.ai.configured:
        return {
            **base,
            "status": "ok",
            "ai": {
                "status": "not_configured",
                "text": None,
            },
        }

    cache = app.state.analysis_cache
    ttl = max(0, get_settings().analysis_cache_ttl_s)

    for key, value in list(cache.items()):
        if (
            not isinstance(value, dict)
            or not isinstance(value.get("ts"), int)
            or now - value["ts"] >= ttl
        ):
            cache.pop(key, None)

    cache_key = hashlib.sha256(
        (language + json.dumps(facts, sort_keys=True, ensure_ascii=False)).encode("utf-8")
    ).hexdigest()
    cached = cache.get(cache_key)

    if (
        cached
        and not body.force
        and now - cached["ts"] < ttl
    ):
        return {
            **base,
            "generated_at": cached["ts"],
            "status": "ok",
            "ai": {
                "status": "ok",
                "text": cached["text"],
                "model": app.state.ai.model,
                "cached": True,
            },
        }

    if _limited(
        _ai_hits,
        _client_ip(request),
        get_settings().ai_rate_limit_per_min,
    ):
        return {
            **base,
            "status": "ok",
            "ai": {
                "status": "rate_limited",
                "text": None,
            },
        }

    try:
        task = ai_mod.ANALYSIS_TASK.format(
            lang=ai_mod.LANG_NAMES[language]
        )

        prompt = ai_mod.system_prompt(
            language,
            facts,
            now,
        )

        text = await app.state.ai.complete(
            prompt,
            [{"role": "user", "content": task}],
        )

    except ai_mod.AiError as error:
        return {
            **base,
            "status": "ok",
            "ai": {
                "status": "error",
                "code": error.code,
                "text": None,
            },
        }

    cache[cache_key] = {
        "ts": now,
        "text": text,
    }
    while len(cache) > 128:
        oldest = min(cache, key=lambda key: cache[key]["ts"])
        cache.pop(oldest, None)

    return {
        **base,
        "status": "ok",
        "ai": {
            "status": "ok",
            "text": text,
            "model": app.state.ai.model,
            "cached": False,
        },
    }


# Development-only endpoint

@app.get("/v1/dev/talasanj-raw")
async def talasanj_raw():
    if get_settings().aurex_env != "dev":
        raise HTTPException(status_code=404)

    try:
        return await app.state.talasanj.fetch_raw()
    except ProviderError:
        raise HTTPException(
            status_code=502,
            detail="provider request failed",
        )
