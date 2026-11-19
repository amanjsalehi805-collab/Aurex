"""SQLite price history. Stores only real, fresh quotes received by the backend."""
import math
import sqlite3
import threading
import time
from pathlib import Path

MIN_POINTS = 2
MIN_SPAN_S = 30 * 60


def summarize(points: list[tuple[int, float]]) -> dict:
    if not points:
        return {"points": 0, "sufficient": False}

    first_ts, first = points[0]
    last_ts, last = points[-1]
    prices = [p for _, p in points]
    span = last_ts - first_ts

    out = {
        "points": len(points),
        "first_ts": first_ts,
        "last_ts": last_ts,
        "span_s": span,
        "first": first,
        "last": last,
        "min": min(prices),
        "max": max(prices),
        "sufficient": len(points) >= MIN_POINTS and span >= MIN_SPAN_S,
    }
    out["change_pct"] = (
        (last - first) / first * 100.0
        if out["sufficient"] and first > 0
        else None
    )
    return out


class HistoryStore:
    def __init__(
        self,
        path: str,
        min_interval_s: int = 300,
        retention_days: int = 90,
    ):
        if min_interval_s < 0 or retention_days < 1:
            raise ValueError("Invalid history retention or interval settings")

        self.path = path
        self.min_interval_s = min_interval_s
        self.retention_s = retention_days * 86400
        self._lock = threading.Lock()

        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)

        self._mem = (
            sqlite3.connect(path, check_same_thread=False)
            if path == ":memory:"
            else None
        )
        self._init()

    def _conn(self) -> sqlite3.Connection:
        return self._mem or sqlite3.connect(self.path, timeout=10)

    def _init(self) -> None:
        with self._lock:
            c = self._conn()
            try:
                c.executescript("""
                    CREATE TABLE IF NOT EXISTS quote_history(
                        asset_id TEXT NOT NULL,
                        ts INTEGER NOT NULL,
                        price REAL NOT NULL,
                        unit TEXT NOT NULL,
                        source TEXT NOT NULL,
                        PRIMARY KEY(asset_id, ts)
                    );
                    CREATE INDEX IF NOT EXISTS idx_hist_asset_ts
                    ON quote_history(asset_id, ts);
                """)
                c.commit()
            finally:
                if self._mem is None:
                    c.close()

    def record(
        self,
        items: list[dict],
        now_ts: int | None = None,
    ) -> int:
        stored = 0
        now = int(time.time()) if now_ts is None else int(now_ts)
        cutoff = now - self.retention_s

        with self._lock:
            c = self._conn()
            try:
                for item in items:
                    if item.get("freshness") == "stale":
                        continue

                    price = item.get("price")
                    if (
                        not isinstance(price, (int, float))
                        or isinstance(price, bool)
                        or not math.isfinite(price)
                        or price <= 0
                    ):
                        continue

                    try:
                        ts = int(item["ts"])
                        asset_id = str(item["asset_id"]).strip()
                        unit = str(item["unit"]).strip()
                        source = str(item["source"]).strip()
                    except (KeyError, TypeError, ValueError, OverflowError):
                        continue

                    if (
                        not asset_id
                        or not unit
                        or not source
                        or ts <= 0
                        or ts > now
                    ):
                        continue

                    row = c.execute(
                        "SELECT ts FROM quote_history "
                        "WHERE asset_id=? ORDER BY ts DESC LIMIT 1",
                        (asset_id,),
                    ).fetchone()

                    if row is not None and ts - row[0] < self.min_interval_s:
                        continue

                    cur = c.execute(
                        "INSERT OR IGNORE INTO quote_history"
                        "(asset_id, ts, price, unit, source) VALUES(?,?,?,?,?)",
                        (asset_id, ts, float(price), unit, source),
                    )
                    stored += cur.rowcount

                c.execute(
                    "DELETE FROM quote_history WHERE ts < ?",
                    (cutoff,),
                )
                c.commit()
            finally:
                if self._mem is None:
                    c.close()

        return stored

    def series(
        self,
        asset_id: str,
        since_ts: int,
        limit: int = 1000,
    ) -> list[tuple[int, float]]:
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise ValueError("limit must be a positive integer")

        with self._lock:
            c = self._conn()
            try:
                rows = c.execute(
                    "SELECT ts, price FROM quote_history "
                    "WHERE asset_id=? AND ts>=? ORDER BY ts ASC",
                    (asset_id, since_ts),
                ).fetchall()
            finally:
                if self._mem is None:
                    c.close()

        if len(rows) > limit:
            if limit == 1:
                rows = [rows[-1]]
            else:
                step = (len(rows) - 1) / (limit - 1)
                rows = [rows[round(i * step)] for i in range(limit)]

        return [(int(ts), float(price)) for ts, price in rows]

    def unit_of(self, asset_id: str) -> str | None:
        with self._lock:
            c = self._conn()
            try:
                row = c.execute(
                    "SELECT unit FROM quote_history "
                    "WHERE asset_id=? ORDER BY ts DESC LIMIT 1",
                    (asset_id,),
                ).fetchone()
            finally:
                if self._mem is None:
                    c.close()

        return row[0] if row else None
