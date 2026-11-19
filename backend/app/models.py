from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Unit(str, Enum):
    IRR = "IRR"  # rial
    IRT = "IRT"  # toman (1 toman = 10 rial)
    USD = "USD"


class Market(str, Enum):
    FREE = "free"
    OFFICIAL = "official"
    GLOBAL = "global"


class Freshness(str, Enum):
    LIVE = "live"          # provider documented as real-time AND recent
    DELAYED = "delayed"    # recent, but not documented as real-time
    STALE = "stale"        # older than the stale threshold
    HISTORICAL = "historical"


class Quote(BaseModel):
    """One price. asset_id encodes market + unit semantics (e.g. usd_free_irt),
    so two providers may only fill the same asset_id if they mean the same thing."""

    asset_id: str
    kind: str                       # currency | gold | coin | index | metal
    market: Market
    unit: Unit
    price: float
    previous_price: float | None = None
    change: float | None = None
    change_pct: float | None = None
    source: str
    source_timestamp: datetime | None = None   # time claimed by the provider
    fetched_at: datetime                       # time AUREX backend got it
    freshness: Freshness = Freshness.DELAYED
    flags: list[str] = Field(default_factory=list)


class QuotesResponse(BaseModel):
    generated_at: datetime
    quotes: list[Quote]
    unavailable: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    stale_after_s: int | None = None
