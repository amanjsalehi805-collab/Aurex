"""Identifier helpers. All entity IDs are canonical lowercase UUIDv4 strings."""

from __future__ import annotations

import uuid
from typing import Any


def new_id() -> str:
    return str(uuid.uuid4())


def is_valid_id(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 36:
        return False
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        return False
    return str(parsed) == value and parsed.version == 4
