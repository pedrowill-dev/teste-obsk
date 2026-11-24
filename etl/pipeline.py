"""The pipeline: extract -> transform -> load, with telemetry and a quality gate."""
import logging
import os

import obskitpy

from .config import Config
from .extract import extract
from .load import load
from .transform import transform

log = logging.getLogger("etl.sales")


class QualityGateError(RuntimeError):
    """Too many rows were rejected: the data is probably broken upstream, so the run must not look like a success."""


def run(config: Config) -> dict[str, int]:
    meter = obskitpy.meter("etl.sales")
    extracted = meter.create_counter("etl.rows.extracted", unit="{row}")
    loaded = meter.create_counter("etl.rows.loaded", unit="{row}")
    rejected_counter = meter.create_counter("etl.rows.rejected", unit="{row}")

    with obskitpy.tracer("etl.sales").start_as_current_span("etl-run") as span:
        span.set_attribute("etl.env", config.env)
        rows = extract(config.source, config.row_limit)
        extracted.add(len(rows))
        orders, rejected = transform(rows)
        rejected_counter.add(len(rejected))
        rate = len(rejected) / len(rows) if rows else 0.0
        log.info("transformed %d rows: %d valid, %d rejected (%.1f%%)", len(rows), len(orders), len(rejected), rate * 100)
        if rate > config.max_reject_rate:
            raise QualityGateError(f"{len(rejected)} of {len(rows)} rows rejected ({rate:.0%}), above the {config.max_reject_rate:.0%} limit; first reason: {rejected[0].reason}")
        total = load(config.warehouse, orders, rejected)
        loaded.add(len(orders))
        log.info("loaded %d orders into %s (warehouse now has %d)", len(orders), config.warehouse.name, total)
        return {"extracted": len(rows), "loaded": len(orders), "rejected": len(rejected), "warehouse_total": total}


def main() -> None:
    config = Config.from_env()
    shutdown = obskitpy.setup(os.environ.get("OTEL_SERVICE_NAME", "etl-vendas"), environment=config.env, version=os.environ.get("OBSKITPY_RELEASE", "0.0.0"))
    try:
        result = run(config)
        log.info("done: %s", result)
    except Exception:
        log.exception("sales ETL failed")
        shutdown()
        raise SystemExit(1) from None
    shutdown()
