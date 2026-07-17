"""SQLite database initialization and CRUD helpers for Book Trading Simulator."""

import sqlite3
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from config import DB_PATH


class Database:
    def __init__(self):
        db_dir = os.path.dirname(DB_PATH)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._db_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._db_conn.row_factory = sqlite3.Row

    def create_schema(self):
        """Create tables and run migrations."""
        self._db_conn.row_factory = sqlite3.Row
        self._db_conn.execute("PRAGMA journal_mode=WAL")
        self._db_conn.executescript("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS holdings (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL UNIQUE,
                quantity INTEGER NOT NULL,
                avg_price REAL NOT NULL,
                total_cost REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS trade_history (
                id TEXT PRIMARY KEY,
                action TEXT NOT NULL CHECK(action IN ('BUY', 'SELL')),
                symbol TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                total_value REAL NOT NULL,
                fund_balance_after REAL NOT NULL,
                timestamp TEXT NOT NULL DEFAULT ''
            );
        """)
        self._migrate()
        self._db_conn.commit()

    def _migrate(self):
        """Add missing columns to existing tables and backfill NULLs."""
        migrations = [
            "ALTER TABLE holdings ADD COLUMN region TEXT DEFAULT 'AU'",
            "ALTER TABLE trade_history ADD COLUMN region TEXT DEFAULT 'AU'",
        ]
        for sql in migrations:
            try:
                self._db_conn.execute(sql)
            except sqlite3.OperationalError:
                pass  # column already exists
        # Backfill NULL values (ALTER TABLE ADD COLUMN leaves NULLs in old rows)
        try:
            self._db_conn.execute("UPDATE holdings SET region = 'AU' WHERE region IS NULL")
            self._db_conn.execute("UPDATE trade_history SET region = 'AU' WHERE region IS NULL")
            self._db_conn.commit()
        except sqlite3.OperationalError:
            pass

    def close(self):
        if self._db_conn:
            self._db_conn.close()
            self._db_conn = None

    #
    # Config (key-value store, same pattern as stock_trading_agent)
    #

    def get_config(self, key: str) -> Optional[str]:
        row = self._db_conn.execute(
            "SELECT value FROM config WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def set_config(self, key: str, value: str):
        self._db_conn.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
            (key, str(value)),
        )
        self._db_conn.commit()

    def get_config_float(self, key: str, default: float = 0.0) -> float:
        val = self.get_config(key)
        return float(val) if val is not None else default

    #
    # Holdings
    #

    def upsert_holding(self, symbol: str, quantity: int, price: float, total_cost: float, region: str = "AU"):
        """Insert or update a holding. On buy of existing symbol, recalculate
        weighted average price and add to quantity."""
        existing = self.get_holding(symbol)
        now = datetime.now(timezone.utc).isoformat()

        if existing:
            new_qty = existing["quantity"] + quantity
            new_total_cost = existing["total_cost"] + total_cost
            new_avg_price = new_total_cost / new_qty if new_qty > 0 else 0.0
            self._db_conn.execute(
                """UPDATE holdings
                   SET quantity = ?, avg_price = ?, total_cost = ?, updated_at = ?, region = ?
                   WHERE symbol = ?""",
                (new_qty, new_avg_price, new_total_cost, now, region.upper(), symbol),
            )
        else:
            holding_id = str(uuid.uuid4())
            self._db_conn.execute(
                """INSERT INTO holdings (id, symbol, quantity, avg_price, total_cost, created_at, updated_at, region)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (holding_id, symbol.upper(), quantity, price, total_cost, now, now, region.upper()),
            )
        self._db_conn.commit()

    def get_holding(self, symbol: str) -> Optional[dict]:
        row = self._db_conn.execute(
            "SELECT * FROM holdings WHERE symbol = ?", (symbol.upper(),)
        ).fetchone()
        return dict(row) if row else None

    def list_holdings(self) -> list[dict]:
        rows = self._db_conn.execute(
            "SELECT * FROM holdings ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def delete_holding(self, symbol: str):
        self._db_conn.execute(
            "DELETE FROM holdings WHERE symbol = ?", (symbol.upper(),)
        )
        self._db_conn.commit()

    #
    # Trade History
    #

    def insert_trade(self, item: dict) -> str:
        trade_id = item.get("id") or str(uuid.uuid4())
        self._db_conn.execute(
            """INSERT INTO trade_history
               (id, action, symbol, quantity, price, total_value, fund_balance_after, region, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trade_id,
                item["action"],
                item["symbol"].upper(),
                item["quantity"],
                item["price"],
                item["total_value"],
                item["fund_balance_after"],
                item.get("region", "AU").upper(),
                item.get("timestamp", datetime.now(timezone.utc).isoformat()),
            ),
        )
        self._db_conn.commit()
        return trade_id

    def list_trades(self, limit: int = 50, offset: int = 0, region: str = None) -> list[dict]:
        if region:
            rows = self._db_conn.execute(
                "SELECT * FROM trade_history WHERE region = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (region.upper(), limit, offset),
            ).fetchall()
        else:
            rows = self._db_conn.execute(
                "SELECT * FROM trade_history ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_trades_by_symbol(self, symbol: str) -> list[dict]:
        rows = self._db_conn.execute(
            "SELECT * FROM trade_history WHERE symbol = ? ORDER BY timestamp DESC",
            (symbol.upper(),),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_db(self):
        """Expose raw connection for health checks."""
        return self._db_conn
