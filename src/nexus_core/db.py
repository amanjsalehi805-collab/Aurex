"""SQLite connection + checksummed migration runner.

SQLite is used for (a) the Phase 1 verified reference implementation of the schema, (b) the
Android agent's local journal, (c) fast tests. The orchestrator targets PostgreSQL from Phase 2;
migrations without a dialect suffix use only the portable SQL subset so they can run on both.
Dialect-specific files are named NNNN_name.sqlite.sql.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .clock import format_ts, utc_now

MIGRATIONS_DIR = Path(__file__).with_name("migrations")
_NAME_RE = re.compile(r"^(\d{4})_([a-z0-9_]+?)(\.sqlite)?\.sql$")


class MigrationError(RuntimeError):
    pass


def connect(path: str | Path = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), isolation_level=None)  # autocommit; explicit transactions
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = FULL")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """BEGIN IMMEDIATE ... COMMIT/ROLLBACK. Not re-entrant."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def _discover(dialect: str) -> list[tuple[str, str, Path]]:
    found: dict[str, tuple[str, str, Path]] = {}
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        match = _NAME_RE.match(path.name)
        if not match:
            raise MigrationError(f"bad migration file name: {path.name}")
        version, name, suffix = match.groups()
        if suffix and suffix != f".{dialect}":
            continue
        if version in found:
            raise MigrationError(f"duplicate migration version {version}")
        found[version] = (version, name, path)
    return [found[v] for v in sorted(found)]


def migrate(conn: sqlite3.Connection, dialect: str = "sqlite") -> list[str]:
    """Apply pending migrations atomically. Returns versions applied this call."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version TEXT PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)"
    )
    applied = {row["version"]: row["checksum"] for row in conn.execute("SELECT * FROM schema_migrations")}
    files = _discover(dialect)
    known = {version for version, _, _ in files}
    unknown = set(applied) - known
    if unknown:
        raise MigrationError(f"database has migrations this code does not know: {sorted(unknown)}")
    done: list[str] = []
    for version, name, path in files:
        sql = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        if version in applied:
            if applied[version] != checksum:
                raise MigrationError(f"migration {version} was modified after it was applied")
            continue
        record = (
            f"INSERT INTO schema_migrations (version, name, checksum, applied_at) "
            f"VALUES ('{version}', '{name}', '{checksum}', '{format_ts(utc_now())}');"
        )
        try:
            conn.executescript(f"BEGIN;\n{sql}\n{record}\nCOMMIT;")
        except sqlite3.Error as exc:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise MigrationError(f"migration {version} failed: {exc}") from exc
        done.append(version)
    return done
