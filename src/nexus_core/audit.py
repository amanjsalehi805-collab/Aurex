"""Hash-chained, append-only audit log (tamper-evident).

Each entry's hash covers the previous entry's hash, so editing or removing a middle entry breaks
verification. The database also blocks UPDATE/DELETE (0002 migration). Truncating the TAIL is not
detectable from the chain alone; Phase 8 anchors the head hash externally.
Details are redacted before storage - secrets never enter the log.
"""

from __future__ import annotations

import hashlib
import sqlite3
from typing import Any

from .clock import Clock, format_ts, utc_now
from .db import transaction
from .ids import new_id
from .messages import canonical_json
from .redaction import Redactor

GENESIS = "0" * 64
ACTOR_TYPES = ("user", "ai", "orchestrator", "worker", "device", "system")


def _entry_hash(prev_hash: str, fields: dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + "\n" + canonical_json(fields)).encode("utf-8")).hexdigest()


class AuditLog:
    def __init__(self, conn: sqlite3.Connection, redactor: Redactor | None = None,
                 clock: Clock = utc_now) -> None:
        self._conn = conn
        self._redactor = redactor or Redactor()
        self._clock = clock

    def append(self, *, owner_id: str, actor_type: str, actor_id: str | None, action: str,
               subject_type: str, subject_id: str | None, details: dict[str, Any] | None = None) -> int:
        if actor_type not in ACTOR_TYPES:
            raise ValueError(f"unknown actor_type {actor_type!r}")
        safe_details = canonical_json(self._redactor.redact_obj(details or {}))
        safe_action = self._redactor.redact(action)
        with transaction(self._conn):
            row = self._conn.execute(
                "SELECT seq, entry_hash FROM audit_log WHERE owner_id = ? ORDER BY seq DESC LIMIT 1",
                (owner_id,),
            ).fetchone()
            seq = (row["seq"] + 1) if row else 1
            prev = row["entry_hash"] if row else GENESIS
            created = format_ts(self._clock())
            fields = {"owner_id": owner_id, "seq": seq, "created_at": created, "actor_type": actor_type,
                      "actor_id": actor_id, "action": safe_action, "subject_type": subject_type,
                      "subject_id": subject_id, "details": safe_details}
            self._conn.execute(
                "INSERT INTO audit_log (id, owner_id, seq, created_at, actor_type, actor_id, action,"
                " subject_type, subject_id, details, prev_hash, entry_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (new_id(), owner_id, seq, created, actor_type, actor_id, safe_action, subject_type,
                 subject_id, safe_details, prev, _entry_hash(prev, fields)),
            )
        return seq

    def verify(self, owner_id: str) -> int | None:
        """Return None if the chain is intact, else the seq of the first bad entry."""
        prev = GENESIS
        expected_seq = 1
        for row in self._conn.execute("SELECT * FROM audit_log WHERE owner_id = ? ORDER BY seq", (owner_id,)):
            if row["seq"] != expected_seq or row["prev_hash"] != prev:
                return row["seq"]
            fields = {"owner_id": row["owner_id"], "seq": row["seq"], "created_at": row["created_at"],
                      "actor_type": row["actor_type"], "actor_id": row["actor_id"], "action": row["action"],
                      "subject_type": row["subject_type"], "subject_id": row["subject_id"],
                      "details": row["details"]}
            if _entry_hash(prev, fields) != row["entry_hash"]:
                return row["seq"]
            prev = row["entry_hash"]
            expected_seq += 1
        return None
