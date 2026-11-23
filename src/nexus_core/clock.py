"""UTC timestamps in one fixed-width format.

Fixed width means plain string comparison in SQL is also chronological comparison.
Format: YYYY-MM-DDTHH:MM:SS.ffffffZ
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Callable

Clock = Callable[[], datetime]

_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_ts(moment: datetime) -> str:
    if moment.tzinfo is None:
        raise ValueError("naive datetime is not allowed")
    return moment.astimezone(timezone.utc).strftime(_FMT)


def parse_ts(value: str) -> datetime:
    if not isinstance(value, str) or not _TS_RE.match(value):
        raise ValueError(f"invalid timestamp: {value!r}")
    return datetime.strptime(value, _FMT).replace(tzinfo=timezone.utc)


def is_valid_ts(value: Any) -> bool:
    try:
        parse_ts(value)
    except ValueError:
        return False
    return True
