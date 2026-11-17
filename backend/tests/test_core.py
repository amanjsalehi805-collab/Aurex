"""All payloads here are SYNTHETIC test fixtures, used only by tests."""
import math
from datetime import datetime, timedelta, timezone

import pytest

from app.models import Freshness, Quote
from app.providers.mapping import normalize, parse_ts, to_float
from app.validation import compute_freshness, finalize_quote, validate_price

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

MAPPING = {
    "items_path": "data",
    "assets": {
        "usd_free_irt": {"kind": "currency", "market": "free", "unit": "IRT",
                         "match_field": "symbol", "match_value": "USD",
                         "price_field": "price", "previous_field": "prev",
                         "timestamp_field": "ts"},
        "eur_free_irt": {"kind": "currency", "market": "free", "unit": "IRT",
                         "match_field": "symbol", "match_value": "EUR",
                         "price_field": "price"},
    },
}


def test_normalize_maps_and_reports_missing():
    raw = {"data": [{"symbol": "USD", "price": "1,000", "prev": 900, "ts": "2026-01-01T11:59:00Z"}]}
    quotes, missing = normalize(raw, MAPPING, "Test", NOW)
    assert [q.asset_id for q in quotes] == ["usd_free_irt"]
    assert quotes[0].price == 1000 and quotes[0].previous_price == 900
    assert missing == ["eur_free_irt"]


def test_normalize_skips_bad_price_instead_of_inventing():
    raw = {"data": [{"symbol": "USD", "price": "n/a"}]}
    quotes, missing = normalize(raw, MAPPING, "Test", NOW)
    assert quotes == [] and "usd_free_irt" in missing


@pytest.mark.parametrize("bad", [0, -5, math.nan, math.inf])
def test_invalid_prices_rejected(bad):
    with pytest.raises(ValueError):
        validate_price(bad)


def test_freshness_levels():
    fresh = NOW - timedelta(seconds=10)
    old = NOW - timedelta(hours=2)
    assert compute_freshness(fresh, fresh, NOW, 900, False) == Freshness.DELAYED
    assert compute_freshness(fresh, fresh, NOW, 900, True) == Freshness.LIVE
    assert compute_freshness(old, fresh, NOW, 900, True) == Freshness.STALE


def test_unusual_change_flag_and_change_math():
    q = Quote(asset_id="a", kind="currency", market="free", unit="IRT", price=130,
              previous_price=100, source="T", fetched_at=NOW)
    out = finalize_quote(q, NOW, 900, 15, False, None)
    assert out.change == 30 and round(out.change_pct) == 30
    assert "unusual_change" in out.flags


def test_to_float_and_ts():
    assert to_float("1,234.5") == 1234.5
    assert parse_ts(1_700_000_000_000).year == 2023
    with pytest.raises(ValueError):
        to_float(True)
