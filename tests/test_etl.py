from decimal import Decimal

import pytest

from etl.config import Config
from etl.extract import extract
from etl.load import load
from etl.pipeline import QualityGateError, run
from etl.transform import parse_amount, parse_date, to_order, transform

GOOD = {"order_id": "1", "customer": "ana souza", "country": "br", "currency": "usd", "amount": "1.234,50", "status": "PAID", "created_at": "03/04/2026"}


def test_amounts_in_every_format_the_export_uses():
    assert parse_amount("1.234,56") == Decimal("1234.56")
    assert parse_amount("1,234.56") == Decimal("1234.56")
    assert parse_amount("1234.56") == Decimal("1234.56")
    with pytest.raises(ValueError):
        parse_amount("N/A")


def test_dates_in_both_formats_and_an_impossible_one():
    assert parse_date("2026-04-03").isoformat() == "2026-04-03" == parse_date("03/04/2026").isoformat()
    with pytest.raises(ValueError):
        parse_date("31/02/2026")


def test_a_good_row_is_normalized_and_converted():
    order = to_order(GOOD)
    assert (order.customer, order.country, order.currency, order.status) == ("Ana Souza", "BR", "USD", "paid")
    assert order.amount_brl == Decimal("6666.30")


@pytest.mark.parametrize("change, reason", [({"customer": ""}, "missing customer"), ({"amount": "-5"}, "positive"), ({"status": "lost"}, "unknown status"),
                                            ({"currency": "XYZ"}, "unknown currency"), ({"order_id": "abc"}, "order_id")])
def test_bad_rows_come_back_with_their_reason(change, reason):
    orders, rejected = transform([{**GOOD, **change}])
    assert orders == [] and reason in rejected[0].reason


def test_a_resent_order_keeps_the_last_version():
    orders, rejected = transform([GOOD, {**GOOD, "amount": "10"}])
    assert len(orders) == 1 and orders[0].amount == Decimal(10) and "duplicate" in rejected[0].reason


def test_loading_twice_changes_nothing(tmp_path):
    orders, rejected = transform([GOOD, {**GOOD, "order_id": "2", "customer": ""}])
    assert load(tmp_path / "w.db", orders, rejected) == 1
    assert load(tmp_path / "w.db", orders, rejected) == 1


def config(tmp_path, **over):
    base = {"env": "dev", "source": tmp_path / "orders.csv", "warehouse": tmp_path / "dev.db", "row_limit": 0, "max_reject_rate": 0.15}
    return Config(**{**base, **over})


def write_csv(path, rows):
    path.write_text("order_id,customer,country,currency,amount,status,created_at\n" + "\n".join(",".join(r) for r in rows) + "\n")


def test_the_pipeline_loads_a_clean_file(tmp_path):
    write_csv(tmp_path / "orders.csv", [["1", "ana", "br", "BRL", "10.00", "paid", "2026-01-01"], ["2", "bruno", "br", "BRL", "20.00", "paid", "2026-01-02"]])
    assert run(config(tmp_path)) == {"extracted": 2, "loaded": 2, "rejected": 0, "warehouse_total": 2}


def test_the_quality_gate_fails_the_run_and_loads_nothing(tmp_path):
    write_csv(tmp_path / "orders.csv", [["1", "", "br", "BRL", "10.00", "paid", "2026-01-01"], ["2", "bruno", "br", "BRL", "20.00", "paid", "2026-01-02"]])
    with pytest.raises(QualityGateError, match="1 of 2 rows rejected"):
        run(config(tmp_path))
    assert not (tmp_path / "dev.db").exists()


def test_the_bundled_export_passes_in_every_size():
    rows = extract(__import__("pathlib").Path("data/orders.csv"))
    assert len(rows) == 1012
    orders, rejected = transform(rows)
    assert len(orders) + len(rejected) == 1012 and len(rejected) / 1012 < 0.15
