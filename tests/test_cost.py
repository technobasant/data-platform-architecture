"""The cost model's arithmetic, checked against numbers worked out by hand from cost/prices.yml."""

from __future__ import annotations

import pytest

from cost.model import TB, TIB, break_even, hourly, load, per_scanned_tb, storage_tb, tier_costs


@pytest.fixture(scope="module")
def inputs():
    return load()


def test_hourly_prices_of_a_medium_engine(inputs) -> None:
    prices, workloads = inputs
    h = hourly(prices, workloads)
    assert h["Snowflake Standard"] == pytest.approx(4 * 2.00)  # 4 credits/h × $2
    assert h["Snowflake Enterprise"] == pytest.approx(4 * 3.00)
    assert h["Databricks SQL Serverless"] == pytest.approx(24 * 0.70)  # 24 DBU/h × $0.70
    assert h["Trino on EC2 (workers only)"] == pytest.approx(4 * 0.5292)


def test_per_tb_scanned(inputs) -> None:
    prices, _ = inputs
    s = per_scanned_tb(prices)
    assert s["BigQuery on-demand"] == pytest.approx(6.25 * 1e12 / 2**40)  # priced per TiB
    assert s["Athena"] == pytest.approx(5.00)


def test_break_even_is_hourly_price_over_scan_price(inputs) -> None:
    prices, workloads = inputs
    b = break_even(prices, workloads)["Snowflake Enterprise"]["tb_per_hour"]
    assert b["Athena"] == pytest.approx(12.00 / 5.00, abs=0.01)
    assert b["BigQuery on-demand"] == pytest.approx(12.00 / (6.25 * TB / TIB), abs=0.01)


def test_storage_grows_with_events_retention_and_derived_tables(inputs) -> None:
    _, workloads = inputs
    tier = {"events_per_day": 30_000_000}
    assert storage_tb(workloads, tier) == pytest.approx(30e6 * 150 * 760 * 1.3 / 1e12)


def test_bigquery_free_tier_is_subtracted_once(inputs) -> None:
    prices, workloads = inputs
    tiny = {"events_per_day": 1, "compute_hours_per_day": 1, "scanned_tb_per_day": 0.01}
    # 0.01 TB a day is 0.28 TiB a month: inside the free TiB, so no query charge.
    assert tier_costs(prices, workloads, tiny)["monthly_usd"]["BigQuery on-demand"]["compute"] == 0


def test_every_price_cites_its_source(inputs) -> None:
    prices, _ = inputs
    for group, items in prices.items():
        if group == "retrieved":
            continue
        for key, item in items.items():
            assert item["source"].startswith("https://"), f"{group}.{key}"
            assert "quote" in item or "note" in item, f"{group}.{key}"


def test_operations_are_added_on_top_of_the_bill(inputs) -> None:
    prices, workloads = inputs
    today = workloads["tiers"]["today"]
    for option, c in tier_costs(prices, workloads, today)["monthly_usd"].items():
        people = workloads["operations_fte"][option] * workloads["engineer_month_usd"]
        assert c["total_with_operations"] == pytest.approx(c["total"] + people, abs=1)
