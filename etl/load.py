"""Load: write into the warehouse. Idempotent: running the same load twice leaves exactly the same rows (the orchestrator may run a job again)."""
import sqlite3
from pathlib import Path

import obskitpy

from .transform import Order, Rejected

SCHEMA = """
CREATE TABLE IF NOT EXISTS fact_orders (
  order_id INTEGER PRIMARY KEY, customer TEXT NOT NULL, country TEXT, currency TEXT NOT NULL, amount TEXT NOT NULL,
  amount_brl TEXT NOT NULL, status TEXT NOT NULL, ordered_on TEXT NOT NULL, loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS rejected_orders (order_id TEXT, reason TEXT, raw TEXT, loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
"""


@obskitpy.traced("load")
def load(path: Path, orders: list[Order], rejected: list[Rejected]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:  # one transaction: all or nothing
        db.executescript(SCHEMA)
        db.executemany(
            "INSERT OR REPLACE INTO fact_orders (order_id, customer, country, currency, amount, amount_brl, status, ordered_on) VALUES (?,?,?,?,?,?,?,?)",
            [(o.order_id, o.customer, o.country, o.currency, str(o.amount), str(o.amount_brl), o.status, o.ordered_on.isoformat()) for o in orders])
        db.execute("DELETE FROM rejected_orders")  # the rejects of the latest run only
        db.executemany("INSERT INTO rejected_orders (order_id, reason, raw) VALUES (?,?,?)", [(r.order_id, r.reason, str(r.raw)) for r in rejected])
        return db.execute("SELECT COUNT(*) FROM fact_orders").fetchone()[0]
