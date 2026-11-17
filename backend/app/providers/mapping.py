"""Declarative mapping from a provider's JSON to AUREX Quotes.

The mapping file is written from a REAL sanitized provider response, never guessed.
Format:
{
  "items_path": "a.b",              # dotted path to list (or dict of items)
  "assets": {
    "usd_free_irt": {
      "kind": "currency", "market": "free", "unit": "IRT",
      "match_field": "symbol", "match_value": "USD",
      "price_field": "price", "previous_field": null, "timestamp_field": null
    }
  }
}
"""
from datetime import datetime, timezone
from typing import Any

from ..models import Market, Quote, Unit


def get_path(obj: Any, path: str | None) -> Any:
    if not path:
        return obj
    for part in path.split("."):
        if isinstance(obj, dict) and part in obj:
            obj = obj[part]
        else:
            raise KeyError(f"path segment '{part}' not found")
    return obj


def to_float(v: Any) -> float:
    if isinstance(v, bool):
        raise ValueError("bool is not a price")
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        return float(v.replace(",", "").strip())
    raise ValueError(f"unsupported price type: {type(v).__name__}")


def parse_ts(v: Any) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        if v > 1e12:  # milliseconds
            v = v / 1000
        return datetime.fromtimestamp(v, tz=timezone.utc)
    if isinstance(v, str):
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def normalize(raw: Any, mapping: dict, source: str, fetched_at: datetime) -> tuple[list[Quote], list[str]]:
    """Returns (quotes, missing_asset_ids). Never invents values."""
    items = get_path(raw, mapping.get("items_path"))
    if isinstance(items, dict):
        items = list(items.values())
    if not isinstance(items, list):
        raise ValueError("items_path does not point to a list")

    quotes: list[Quote] = []
    missing: list[str] = []
    for asset_id, spec in mapping.get("assets", {}).items():
        found = next(
            (i for i in items if isinstance(i, dict)
             and str(i.get(spec["match_field"])) == str(spec["match_value"])),
            None,
        )
        if found is None or found.get(spec["price_field"]) is None:
            missing.append(asset_id)
            continue
        try:
            price = to_float(found[spec["price_field"]])
            prev_f = spec.get("previous_field")
            prev = to_float(found[prev_f]) if prev_f and found.get(prev_f) is not None else None
            ts_f = spec.get("timestamp_field")
            ts = parse_ts(found.get(ts_f)) if ts_f else None
        except (ValueError, TypeError):
            missing.append(asset_id)
            continue
        quotes.append(Quote(
            asset_id=asset_id, kind=spec["kind"], market=Market(spec["market"]),
            unit=Unit(spec["unit"]), price=price, previous_price=prev,
            source=source, source_timestamp=ts, fetched_at=fetched_at,
        ))
    return quotes, missing
