"""Iranian stock infrastructure. No provider means no stock prices."""
import math
import re
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path

_SYMBOL_RE = re.compile(r"[\w\u200c\u200d\u0600-\u06FF \-]{1,32}", re.UNICODE)


def valid_symbol(symbol: str) -> bool:
    return (
        isinstance(symbol, str)
        and bool(_SYMBOL_RE.fullmatch(symbol.strip()))
    )


class StockProvider(ABC):
    name: str = "stock-provider"

    @abstractmethod
    async def fetch(self, symbols: list[str]) -> list[dict]:
        """Return quotes from a verified source."""


class StockService:
    def __init__(
        self,
        path: str,
        provider: StockProvider | None = None,
        retention_days: int = 365,
    ):
        if retention_days < 1:
            raise ValueError("retention_days must be positive")

        self.path = path
        self.provider = provider
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

    def _conn(self):
        return self._mem or sqlite3.connect(self.path, timeout=10)

    def _done(self, conn):
        if self._mem is None:
            conn.close()

    def _init(self):
        with self._lock:
            conn = self._conn()
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS stock_symbols(
                        symbol TEXT PRIMARY KEY,
                        name TEXT,
                        market TEXT,
                        added_at INTEGER NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS stock_quotes(
                        symbol TEXT PRIMARY KEY,
                        price REAL NOT NULL,
                        previous_close REAL,
                        volume REAL,
                        source TEXT NOT NULL,
                        source_ts INTEGER,
                        fetched_at INTEGER NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS stock_history(
                        symbol TEXT NOT NULL,
                        ts INTEGER NOT NULL,
                        price REAL NOT NULL,
                        PRIMARY KEY(symbol, ts)
                    );
                """)
                conn.commit()
            finally:
                self._done(conn)

    def status(self) -> dict:
        if self.provider is None:
            return {
                "provider_configured": False,
                "provider": None,
                "message": (
                    "No verified Iranian stock data source is connected. "
                    "No prices are available."
                ),
            }
        return {
            "provider_configured": True,
            "provider": self.provider.name,
            "message": None,
        }

    def add_symbol(
        self,
        symbol: str,
        name: str | None = None,
        market: str | None = None,
    ) -> bool:
        symbol = symbol.strip() if isinstance(symbol, str) else ""
        if not valid_symbol(symbol):
            raise ValueError("invalid symbol")
        if name is not None and (
            not isinstance(name, str) or len(name) > 80
        ):
            raise ValueError("invalid name")
        if market is not None and (
            not isinstance(market, str) or len(market) > 80
        ):
            raise ValueError("invalid market")

        with self._lock:
            conn = self._conn()
            try:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO stock_symbols"
                    "(symbol,name,market,added_at) VALUES(?,?,?,?)",
                    (symbol, name, market, int(time.time())),
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                self._done(conn)

    def remove_symbol(self, symbol: str) -> bool:
        with self._lock:
            conn = self._conn()
            try:
                cur = conn.execute(
                    "DELETE FROM stock_symbols WHERE symbol=?",
                    (symbol,),
                )
                conn.execute(
                    "DELETE FROM stock_quotes WHERE symbol=?",
                    (symbol,),
                )
                conn.execute(
                    "DELETE FROM stock_history WHERE symbol=?",
                    (symbol,),
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                self._done(conn)

    def symbols(self) -> list[dict]:
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute(
                    "SELECT symbol,name,market,added_at "
                    "FROM stock_symbols ORDER BY symbol"
                ).fetchall()
            finally:
                self._done(conn)

        return [
            {"symbol": s, "name": n, "market": m, "added_at": a}
            for s, n, m, a in rows
        ]

    def store_quotes(
        self,
        items: list[dict],
        source: str,
        now_ts: int | None = None,
    ) -> int:
        now = int(time.time()) if now_ts is None else int(now_ts)
        if now <= 0 or not isinstance(source, str) or not source.strip():
            return 0

        stored = 0
        with self._lock:
            conn = self._conn()
            try:
                known = {
                    row[0]
                    for row in conn.execute(
                        "SELECT symbol FROM stock_symbols"
                    )
                }

                for item in items:
                    if not isinstance(item, dict):
                        continue

                    symbol = item.get("symbol")
                    if not valid_symbol(symbol):
                        continue
                    symbol = symbol.strip()
                    price = item.get("price")
                    previous = item.get("previous_close")
                    volume = item.get("volume")
                    source_ts = item.get("source_ts")

                    if (
                        symbol not in known
                        or not isinstance(price, (int, float))
                        or isinstance(price, bool)
                        or not math.isfinite(price)
                        or price <= 0
                    ):
                        continue

                    if previous is not None and (
                        not isinstance(previous, (int, float))
                        or isinstance(previous, bool)
                        or not math.isfinite(previous)
                        or previous <= 0
                    ):
                        previous = None

                    if volume is not None and (
                        not isinstance(volume, (int, float))
                        or isinstance(volume, bool)
                        or not math.isfinite(volume)
                        or volume < 0
                    ):
                        volume = None

                    if source_ts is not None and (
                        not isinstance(source_ts, int)
                        or isinstance(source_ts, bool)
                        or source_ts <= 0
                        or source_ts > now
                    ):
                        source_ts = None

                    conn.execute(
                        "INSERT OR REPLACE INTO stock_quotes "
                        "VALUES(?,?,?,?,?,?,?)",
                        (
                            symbol,
                            float(price),
                            previous,
                            volume,
                            source.strip(),
                            source_ts,
                            now,
                        ),
                    )
                    conn.execute(
                        "INSERT OR IGNORE INTO stock_history VALUES(?,?,?)",
                        (symbol, now, float(price)),
                    )
                    stored += 1

                conn.execute(
                    "DELETE FROM stock_history WHERE ts < ?",
                    (now - self.retention_s,),
                )
                conn.commit()
            finally:
                self._done(conn)

        return stored

    def quotes(self) -> list[dict]:
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute(
                    "SELECT q.symbol,s.name,q.price,q.previous_close,"
                    "q.volume,q.source,q.source_ts,q.fetched_at "
                    "FROM stock_quotes q "
                    "JOIN stock_symbols s ON s.symbol=q.symbol "
                    "ORDER BY q.symbol"
                ).fetchall()
            finally:
                self._done(conn)

        result = []
        for sym, name, price, prev, volume, source, source_ts, fetched in rows:
            change = (
                (price - prev) / prev * 100
                if prev is not None and prev > 0
                else None
            )
            result.append({
                "symbol": sym,
                "name": name,
                "price": price,
                "previous_close": prev,
                "change_pct": change,
                "volume": volume,
                "source": source,
                "source_ts": source_ts,
                "fetched_at": fetched,
            })
        return result

    def history(self, symbol: str, since_ts: int) -> list[tuple[int, float]]:
        with self._lock:
            conn = self._conn()
            try:
                rows = conn.execute(
                    "SELECT ts,price FROM stock_history "
                    "WHERE symbol=? AND ts>=? ORDER BY ts",
                    (symbol, since_ts),
                ).fetchall()
            finally:
                self._done(conn)

        return [(int(ts), float(price)) for ts, price in rows]

    async def refresh(self) -> int:
        if self.provider is None:
            return 0

        symbols = [item["symbol"] for item in self.symbols()]
        if not symbols:
            return 0

        items = await self.provider.fetch(symbols)
        return self.store_quotes(items, self.provider.name)
