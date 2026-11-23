"""Durable execution journal + idempotency for the executing side (Android agent / worker).

Rule: a command is journaled as 'started' BEFORE it runs. If the process dies mid-run, recovery
marks it 'unknown'. 'unknown' is never re-executed automatically - a lost response must not
cause a (possibly destructive) command to run twice.
"""

from __future__ import annotations

import enum
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

from .clock import Clock, format_ts, utc_now
from .outcomes import ExecutionStatus, OutcomeError, validate_outcome

_SCHEMA = """
CREATE TABLE IF NOT EXISTS journal (
  idempotency_key TEXT PRIMARY KEY,
  command_id TEXT NOT NULL UNIQUE,
  command TEXT NOT NULL,
  cwd TEXT NOT NULL,
  target TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN
    ('started','succeeded','failed','timed_out','cancelled','not_executed','unknown')),
  exit_code INTEGER,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  duration_ms INTEGER,
  reported INTEGER NOT NULL DEFAULT 0 CHECK (reported IN (0, 1))
);
"""


class JournalConflict(RuntimeError):
    pass


class Decision(str, enum.Enum):
    EXECUTE = "execute"
    ALREADY_FINISHED = "already_finished"
    IN_PROGRESS = "in_progress"
    NEEDS_REVIEW = "needs_review"  # previous run interrupted; outcome unknown; do NOT re-run


@dataclass(frozen=True)
class JournalRecord:
    idempotency_key: str
    command_id: str
    command: str
    cwd: str
    target: str
    status: str
    exit_code: int | None
    started_at: str
    finished_at: str | None
    duration_ms: int | None
    reported: bool


@dataclass(frozen=True)
class BeginResult:
    decision: Decision
    record: JournalRecord


def _record(row: sqlite3.Row) -> JournalRecord:
    return JournalRecord(
        row["idempotency_key"], row["command_id"], row["command"], row["cwd"], row["target"],
        row["status"], row["exit_code"], row["started_at"], row["finished_at"],
        row["duration_ms"], bool(row["reported"]),
    )


class ExecutionJournal:
    def __init__(self, path: str | Path, clock: Clock = utc_now) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if str(path) != ":memory:":
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA synchronous = FULL")
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def _get(self, key: str) -> JournalRecord | None:
        row = self._conn.execute("SELECT * FROM journal WHERE idempotency_key = ?", (key,)).fetchone()
        return _record(row) if row else None

    def begin(self, idempotency_key: str, command_id: str, command: str, cwd: str,
              target: str) -> BeginResult:
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO journal (idempotency_key, command_id, command, cwd, target, status, started_at)"
                    " VALUES (?, ?, ?, ?, ?, 'started', ?)",
                    (idempotency_key, command_id, command, cwd, target, format_ts(self._clock())),
                )
            except sqlite3.IntegrityError:
                existing = self._get(idempotency_key)
                if existing is None:
                    raise JournalConflict("command_id already used under a different key") from None
                if (existing.command, existing.cwd, existing.target, existing.command_id) != (
                        command, cwd, target, command_id):
                    raise JournalConflict("idempotency key reused for a different command") from None
                if existing.status == "started":
                    return BeginResult(Decision.IN_PROGRESS, existing)
                if existing.status == "unknown":
                    return BeginResult(Decision.NEEDS_REVIEW, existing)
                return BeginResult(Decision.ALREADY_FINISHED, existing)
            record = self._get(idempotency_key)
            assert record is not None
            return BeginResult(Decision.EXECUTE, record)

    def finish(self, idempotency_key: str, status: ExecutionStatus | str, exit_code: int | None,
               duration_ms: int | None = None) -> JournalRecord:
        with self._lock:
            current = self._get(idempotency_key)
            if current is None:
                raise JournalConflict("unknown idempotency key")
            if current.status != "started":
                raise JournalConflict(f"cannot finish a record in status {current.status!r}")
            finished = format_ts(self._clock())
            try:
                st = validate_outcome(status, exit_code, started_at=current.started_at, finished_at=finished)
            except OutcomeError as exc:
                raise JournalConflict(str(exc)) from exc
            self._conn.execute(
                "UPDATE journal SET status=?, exit_code=?, finished_at=?, duration_ms=? WHERE idempotency_key=?",
                (st.value, exit_code, finished, duration_ms, idempotency_key),
            )
            result = self._get(idempotency_key)
            assert result is not None
            return result

    def recover_interrupted(self) -> list[JournalRecord]:
        """Call once at startup: anything still 'started' died mid-run and is now 'unknown'."""
        with self._lock:
            rows = self._conn.execute("SELECT idempotency_key FROM journal WHERE status = 'started'").fetchall()
            self._conn.execute("UPDATE journal SET status='unknown', exit_code=NULL WHERE status='started'")
            return [r for r in (self._get(row["idempotency_key"]) for row in rows) if r]

    def mark_reported(self, idempotency_key: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE journal SET reported=1 WHERE idempotency_key=?", (idempotency_key,))

    def unreported(self) -> list[JournalRecord]:
        """Finished/unknown records the cloud has not acknowledged yet (resend after reconnect)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM journal WHERE reported = 0 AND status <> 'started' ORDER BY started_at"
            ).fetchall()
            return [_record(r) for r in rows]
