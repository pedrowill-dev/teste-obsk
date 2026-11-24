"""Transform: clean, validate and de-duplicate. Bad rows are not dropped silently: each one comes back with the reason it was rejected."""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import obskitpy

RATES_TO_BRL = {"BRL": Decimal(1), "USD": Decimal("5.40"), "EUR": Decimal("5.90")}
STATUSES = {"paid", "shipped", "cancelled", "refunded"}


@dataclass(frozen=True)
class Order:
    order_id: int
    customer: str
    country: str
    currency: str
    amount: Decimal
    amount_brl: Decimal
    status: str
    ordered_on: date


@dataclass(frozen=True)
class Rejected:
    order_id: str
    reason: str
    raw: dict[str, str]


def parse_amount(text: str) -> Decimal:
    """Accepts '1.234,56', '1,234.56' and '1234.56'."""
    cleaned = text.strip().replace(" ", "")
    if "," in cleaned and "." in cleaned:
        decimal_sep = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
        thousands = "." if decimal_sep == "," else ","
        cleaned = cleaned.replace(thousands, "").replace(decimal_sep, ".")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"invalid amount {text!r}") from None


def parse_date(text: str) -> date:
    for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text.strip(), pattern).date()
        except ValueError:
            continue
    raise ValueError(f"invalid date {text!r}")


def to_order(raw: dict[str, str]) -> Order:
    """One raw row to a valid Order, or ValueError with the reason."""
    try:
        order_id = int(raw["order_id"])
    except (KeyError, ValueError):
        raise ValueError("missing or invalid order_id") from None
    customer = (raw.get("customer") or "").strip()
    if not customer:
        raise ValueError("missing customer")
    currency = (raw.get("currency") or "BRL").strip().upper()
    if currency not in RATES_TO_BRL:
        raise ValueError(f"unknown currency {currency!r}")
    amount = parse_amount(raw.get("amount") or "")
    if amount <= 0:
        raise ValueError("amount must be positive")
    status = (raw.get("status") or "").strip().lower()
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}")
    return Order(order_id, customer.title(), (raw.get("country") or "").strip().upper(), currency, amount,
                 (amount * RATES_TO_BRL[currency]).quantize(Decimal("0.01")), status, parse_date(raw.get("created_at") or ""))


@obskitpy.traced("transform")
def transform(rows: list[dict[str, str]]) -> tuple[list[Order], list[Rejected]]:
    good: dict[int, Order] = {}
    rejected: list[Rejected] = []
    for raw in rows:
        try:
            order = to_order(raw)
        except ValueError as exc:
            rejected.append(Rejected(raw.get("order_id", "?"), str(exc), raw))
            continue
        if order.order_id in good:  # a re-sent order: the last version wins
            rejected.append(Rejected(str(order.order_id), "duplicate (replaced by the later row)", raw))
        good[order.order_id] = order
    return list(good.values()), rejected
