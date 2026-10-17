"""SQLite storage for canonical items, store rules and prices."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    free_delivery_from REAL,
    delivery_fee REAL NOT NULL DEFAULT 0,
    min_order REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    canonical_name TEXT NOT NULL UNIQUE,
    brand TEXT,
    category TEXT,
    unit TEXT,
    volume REAL
);

CREATE TABLE IF NOT EXISTS prices (
    store_id INTEGER NOT NULL REFERENCES stores(id),
    item_id INTEGER NOT NULL REFERENCES items(id),
    price_rub REAL NOT NULL,
    old_price_rub REAL,
    discount_percent INTEGER,
    promo_end TEXT,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (store_id, item_id)
);
"""


def connect(db_path: str | Path = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection):
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def upsert_store(conn, name, *, free_delivery_from=None, delivery_fee=0.0, min_order=0.0) -> int:
    conn.execute(
        """INSERT INTO stores (name, free_delivery_from, delivery_fee, min_order)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(name) DO UPDATE SET
             free_delivery_from=excluded.free_delivery_from,
             delivery_fee=excluded.delivery_fee,
             min_order=excluded.min_order""",
        (name, free_delivery_from, delivery_fee, min_order),
    )
    row = conn.execute("SELECT id FROM stores WHERE name = ?", (name,)).fetchone()
    return int(row["id"])


def upsert_item(conn, canonical_name, *, brand=None, category=None, unit=None, volume=None) -> int:
    conn.execute(
        """INSERT INTO items (canonical_name, brand, category, unit, volume)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(canonical_name) DO UPDATE SET
             brand=excluded.brand, category=excluded.category,
             unit=excluded.unit, volume=excluded.volume""",
        (canonical_name, brand, category, unit, volume),
    )
    row = conn.execute(
        "SELECT id FROM items WHERE canonical_name = ?", (canonical_name,)
    ).fetchone()
    return int(row["id"])


def upsert_price(
    conn,
    store_id,
    item_id,
    price_rub,
    *,
    old_price_rub=None,
    discount_percent=None,
    promo_end=None,
):
    cols = "store_id, item_id, price_rub, old_price_rub, discount_percent, promo_end"
    conn.execute(
        f"""INSERT INTO prices ({cols})
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(store_id, item_id) DO UPDATE SET
              price_rub=excluded.price_rub,
              old_price_rub=excluded.old_price_rub,
              discount_percent=excluded.discount_percent,
              promo_end=excluded.promo_end,
              fetched_at=datetime('now')""",
        (store_id, item_id, price_rub, old_price_rub, discount_percent, promo_end),
    )


def load_prices(conn) -> dict[int, dict[int, float]]:
    out: dict[int, dict[int, float]] = {}
    for row in conn.execute("SELECT store_id, item_id, price_rub FROM prices"):
        out.setdefault(int(row["store_id"]), {})[int(row["item_id"])] = float(row["price_rub"])
    return out


def load_store_rules(conn) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for row in conn.execute(
        "SELECT id, name, free_delivery_from, delivery_fee, min_order FROM stores"
    ):
        out[int(row["id"])] = {
            "name": row["name"],
            "free_delivery_from": row["free_delivery_from"],
            "delivery_fee": float(row["delivery_fee"]),
            "min_order": float(row["min_order"]),
        }
    return out
