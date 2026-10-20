"""The cost model's arithmetic, checked against numbers worked out by hand from cost/prices.yml."""

from __future__ import annotations

import pytest

from cost.model import break_even, hourly, load, per_scanned_tb, storage_tb, tier_costs


@pytest.fixture(scope="module")
def inputs():
    return load()


def test_hourly_prices_of_a_medium_engine(inputs) -> None:
    prices, workloads = inputs
    h = hourly(prices, workloads)
    assert h["Snowflake Enterprise"] == pytest.approx(4 * 3.90)  # 4 credits/h × $3.90, EU Dublin
    assert h["Snowflake Business Critical"] == pytest.approx(4 * 5.20)
    assert h["Databricks SQL Serverless"] == pytest.approx(24 * 0.91)  # 24 DBU/h × $0.91, EU Ireland
    assert h["Trino on EC2 (workers only)"] == pytest.approx(4 * 0.5922)


def test_per_tb_scanned(inputs) -> None:
    prices, _ = inputs
    assert per_scanned_tb(prices) == {"Athena": pytest.approx(5.00)}


def test_break_even_is_hourly_price_over_scan_price(inputs) -> None:
    prices, workloads = inputs
    b = break_even(prices, workloads)["Snowflake Enterprise"]["tb_per_hour"]
    assert b["Athena"] == pytest.approx(15.60 / 5.00, abs=0.01)


def test_storage_grows_with_events_retention_and_derived_tables(inputs) -> None:
    _, workloads = inputs
    tier = {"events_per_day": 30_000_000}
    assert storage_tb(workloads, tier) == pytest.approx(30e6 * 150 * 760 * 1.3 / 1e12)


def test_only_options_that_can_meet_the_requirements_are_priced(inputs) -> None:
    prices, workloads = inputs
    options = set(tier_costs(prices, workloads, workloads["tiers"]["today"])["monthly_usd"])
    # Snowflake Standard lacks masking, row access policies and Time Travel past a day;
    # BigQuery would take the data out of the company's AWS account (0006).
    assert options == {"Snowflake Enterprise", "Snowflake Business Critical",
                       "Databricks SQL Serverless", "Trino on EC2", "Athena"}  # fmt: skip


def test_every_price_cites_its_source(inputs) -> None:
    prices, _ = inputs
    for group, items in prices.items():
        if not isinstance(items, dict):  # retrieved, region
            continue
        for key, item in items.items():
            source = item["source"]
            assert source.startswith("https://") or "system.billing.list_prices" in source, f"{group}.{key}"
            assert "quote" in item or "note" in item, f"{group}.{key}"


def test_operations_are_added_on_top_of_the_bill(inputs) -> None:
    prices, workloads = inputs
    today = workloads["tiers"]["today"]
    for option, c in tier_costs(prices, workloads, today)["monthly_usd"].items():
        people = workloads["operations_fte"][option] * workloads["engineer_month_usd"]
        assert c["total_with_operations"] == pytest.approx(c["total"] + people, abs=1)
