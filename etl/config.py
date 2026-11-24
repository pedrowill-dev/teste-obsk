"""Settings of a run, read from the environment. The orchestrator sets them per environment (dev / hmg / prd)."""
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    env: str
    source: Path
    warehouse: Path
    row_limit: int          # 0 = every row
    max_reject_rate: float  # the quality gate: a run that rejects more than this fails

    @classmethod
    def from_env(cls) -> "Config":
        env = os.environ.get("OBSKITPY_ENV", "dev")
        warehouse_dir = Path(os.environ.get("ETL_WAREHOUSE_DIR", ROOT / "warehouse"))
        return cls(env=env, source=Path(os.environ.get("ETL_SOURCE", ROOT / "data" / "orders.csv")), warehouse=warehouse_dir / f"{env}.db",
                   row_limit=int(os.environ.get("ETL_ROW_LIMIT", "0")), max_reject_rate=float(os.environ.get("ETL_MAX_REJECT_RATE", "0.15")))
