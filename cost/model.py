"""Monthly cost of the analytical layer on five engines, from list prices.

Two outputs:

  break-even   how many TB one hour of a medium-sized engine must scan before per-scan
               pricing (BigQuery on-demand, Athena) costs more than paying for the hour.
               This depends only on list prices, so it is the robust result.
  tiers        monthly cost for the three workload tiers of docs/context.md. These rest
               on an assumed ratio of data scanned to engine-hours, which nothing here
               measured; the output prints that ratio next to the result.

    python cost/model.py            # print, and write results/cost.json
    python cost/model.py --check    # fail if results/cost.json is out of date
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TB, GIB, TIB = 1e12, 2**30, 2**40
RESULT = ROOT / "results" / "cost.json"


def load() -> tuple[dict, dict]:
    prices = yaml.safe_load((Path(__file__).parent / "prices.yml").read_text())
    workloads = yaml.safe_load((Path(__file__).parent / "workloads.yml").read_text())
    return prices, workloads


def p(prices: dict, path: str) -> float:
    group, key = path.split(".")
    return float(prices[group][key]["value"])


def hourly(prices: dict, workloads: dict) -> dict[str, float]:
    """USD for one hour of a medium-sized engine, per time-billed option."""
    workers = workloads["medium_engine_hour"]["trino_workers_r7i_2xlarge"]
    medium_credits = p(prices, "snowflake.medium_warehouse_credits_per_hour")
    return {
        "Snowflake Standard": medium_credits * p(prices, "snowflake.credit_standard"),
        "Snowflake Enterprise": medium_credits * p(prices, "snowflake.credit_enterprise"),
        "Databricks SQL Serverless": p(prices, "databricks.medium_warehouse_dbu_per_hour")
        * p(prices, "databricks.sql_serverless_per_dbu"),
        "Trino on EC2 (workers only)": workers * p(prices, "aws.ec2_r7i_2xlarge_per_hour"),
    }


def per_scanned_tb(prices: dict) -> dict[str, float]:
    """USD per TB scanned, per scan-billed option (ignoring free tiers)."""
    return {
        "BigQuery on-demand": p(prices, "bigquery.on_demand_per_tib") * TB / TIB,
        "Athena": p(prices, "aws.athena_per_tb_scanned"),
    }


def break_even(prices: dict, workloads: dict) -> dict:
    scan = per_scanned_tb(prices)
    return {
        engine: {
            "usd_per_hour": round(usd, 4),
            "tb_per_hour": {s: round(usd / rate, 2) for s, rate in scan.items()},
        }  # fmt: skip
        for engine, usd in hourly(prices, workloads).items()
    }


def storage_tb(workloads: dict, tier: dict) -> float:
    events = tier["events_per_day"] * workloads["stored_bytes_per_event"] * workloads["retention_days"]
    return events * (1 + workloads["derived_storage_share"]) / TB


def tier_costs(prices: dict, workloads: dict, tier: dict) -> dict:
    days = workloads["days_per_month"]
    hours = tier["compute_hours_per_day"] * days
    scanned_tb = tier["scanned_tb_per_day"] * days
    stored = storage_tb(workloads, tier)
    s3 = stored * 1000 * p(prices, "aws.s3_standard_per_gb_month")
    rates = hourly(prices, workloads)
    coordinator = p(prices, "aws.ec2_m7i_2xlarge_per_hour") * 24 * days
    free_tib = p(prices, "bigquery.on_demand_free_tib_per_month")
    bq_scan = max(0.0, scanned_tb * TB / TIB - free_tib) * p(prices, "bigquery.on_demand_per_tib")
    costs = {
        "Snowflake Standard": (
            hours * rates["Snowflake Standard"],
            stored * p(prices, "snowflake.storage_per_tb_month"),
        ),  # fmt: skip
        "Snowflake Enterprise": (
            hours * rates["Snowflake Enterprise"],
            stored * p(prices, "snowflake.storage_per_tb_month"),
        ),  # fmt: skip
        "Databricks SQL Serverless": (hours * rates["Databricks SQL Serverless"], s3),
        "Trino on EC2": (hours * rates["Trino on EC2 (workers only)"] + coordinator, s3),
        "BigQuery on-demand": (
            bq_scan,
            stored * TB / GIB * p(prices, "bigquery.active_physical_storage_per_gib_month"),
        ),  # fmt: skip
        "Athena": (scanned_tb * p(prices, "aws.athena_per_tb_scanned"), s3),
    }
    return {
        "storage_tb": round(stored, 3),
        "assumed_tb_scanned_per_engine_hour": round(
            tier["scanned_tb_per_day"] / tier["compute_hours_per_day"], 3
        ),
        "monthly_usd": {
            name: {"compute": round(c), "storage": round(s), "total": round(c + s)}
            for name, (c, s) in costs.items()
        },  # fmt: skip
    }


def run() -> dict:
    prices, workloads = load()
    return {
        "prices_retrieved": prices["retrieved"],
        "break_even": break_even(prices, workloads),
        "tiers": {name: tier_costs(prices, workloads, t) for name, t in workloads["tiers"].items()},
    }


def report(r: dict) -> str:
    lines = [
        f"List prices retrieved {r['prices_retrieved']}.",
        "",
        "Break-even: TB one medium engine-hour must scan before per-scan pricing costs more",
        "",
    ]
    for engine, b in r["break_even"].items():
        tb = ", ".join(f"{k} {v} TB" for k, v in b["tb_per_hour"].items())
        lines.append(f"  {engine:<30} ${b['usd_per_hour']:>6.2f}/h   {tb}")
    for name, t in r["tiers"].items():
        lines += ["", f"{name}: {t['storage_tb']} TB stored, assumes "
                  f"{t['assumed_tb_scanned_per_engine_hour']} TB scanned per engine-hour"]  # fmt: skip
        for option, c in sorted(t["monthly_usd"].items(), key=lambda kv: kv[1]["total"]):
            split = f"compute ${c['compute']:,}, storage ${c['storage']:,}"
            lines.append(f"  {option:<28} ${c['total']:>8,}/month  ({split})")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    r = run()
    print(report(r))
    text = json.dumps(r, indent=2) + "\n"
    if args.check:
        if not RESULT.exists() or RESULT.read_text() != text:
            sys.exit("results/cost.json is out of date: run python cost/model.py")
        print("\nmatches results/cost.json")
        return
    RESULT.parent.mkdir(exist_ok=True)
    RESULT.write_text(text)


if __name__ == "__main__":
    main()
