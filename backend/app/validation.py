import math
from datetime import datetime

from .models import Freshness, Quote


def validate_price(price: float) -> None:
    if price is None or isinstance(price, bool):
        raise ValueError("price missing")
    if math.isnan(price) or math.isinf(price) or price <= 0:
        raise ValueError(f"invalid price: {price}")


def unusual_change_flag(price: float, reference: float | None, max_pct: float) -> bool:
    if not reference or reference <= 0:
        return False
    return abs(price - reference) / reference * 100 > max_pct


def compute_freshness(
    source_ts: datetime | None,
    fetched_at: datetime,
    now: datetime,
    stale_after_s: int,
    provider_is_realtime: bool,
) -> Freshness:
    # Use the provider's own timestamp when given; otherwise our fetch time.
    reference = source_ts or fetched_at
    if (now - reference).total_seconds() > stale_after_s:
        return Freshness.STALE
    return Freshness.LIVE if provider_is_realtime else Freshness.DELAYED


def finalize_quote(
    q: Quote,
    now: datetime,
    stale_after_s: int,
    max_change_pct: float,
    provider_is_realtime: bool,
    last_known: Quote | None,
) -> Quote:
    validate_price(q.price)
    if q.previous_price is not None:
        validate_price(q.previous_price)
        q.change = q.price - q.previous_price
        q.change_pct = q.change / q.previous_price * 100
    q.freshness = compute_freshness(
        q.source_timestamp, q.fetched_at, now, stale_after_s, provider_is_realtime
    )
    ref = last_known.price if last_known else q.previous_price
    if unusual_change_flag(q.price, ref, max_change_pct):
        q.flags.append("unusual_change")
    return q
