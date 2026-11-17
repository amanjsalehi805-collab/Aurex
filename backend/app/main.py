import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .config import get_settings
from .providers.base import ProviderError
from .providers.talasanj import TalasanjProvider
from .registry import Registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    talasanj = TalasanjProvider(
        s.talasanj_api_key, s.talasanj_base_url, s.talasanj_min_interval_s,
        s.http_timeout_s, s.http_retries)
    app.state.talasanj = talasanj
    app.state.registry = Registry([talasanj], s)  # add providers here, in priority order
    yield


app = FastAPI(title="AUREX backend", version="0.1.0", lifespan=lifespan)

_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def client_rate_limit(request: Request, call_next):
    limit = get_settings().client_rate_limit_per_min
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= limit:
        return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
    q.append(now)
    return await call_next(request)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/v1/providers/health")
async def providers_health():
    return [h.__dict__ for h in app.state.registry.health()]


@app.get("/v1/quotes")
async def quotes():
    return await app.state.registry.quotes()


@app.get("/v1/dev/talasanj-raw")
async def talasanj_raw():
    """Local development only: returns the provider's raw JSON so a mapping can be
    written from real data. Disabled unless AUREX_ENV=dev."""
    if get_settings().aurex_env != "dev":
        raise HTTPException(status_code=404)
    try:
        return await app.state.talasanj.fetch_raw()
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))
