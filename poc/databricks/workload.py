"""The Databricks half of the proof of concept (decision 0005): speed and cost.

Criteria 6 and 5, on the brief's data at today's scale, in the schema workspace.dpa_bi:

  load   plans, 6,000 accounts, 60,000 users, two years of invoices and 90 days of events
         (31.5 million, 2 July to 29 September 2026), made as baseline/load.sql and
         baseline/events.sql make them for Postgres, and the usage mart (fct_daily_usage,
         models/contracts/usage-mart.odcs.yaml) built from them.
  speed  the BI query set of baseline/analytics.sql, unchanged but for the timestamp
         literals, by 2 and by 8 analysts at once, after one warm-up pass. Timings are the
         warehouse's own, from system.query.history.
  day    from a stopped warehouse, at the start of an hour: the daily build (30 September's
         350,000 events loaded by REPLACE WHERE, the mart's last three days replaced, as
         decision 0008 has it, and the contract's quality check), then the BI query set once
         by each of two analysts; then the warehouse is left to stop itself.
  compare  the Postgres side of the speed comparison, refreshed from the baseline's results.
  bill   what system.billing.usage charged for that hour, against the warehouse's uptime from
         system.compute.warehouse_events and its busy time from system.query.history. Run it
         a few hours after `day`: the billing table lags.

    python poc/databricks/workload.py load speed day     # then, hours later:
    python poc/databricks/workload.py bill

Needs DATABRICKS_HOST, DATABRICKS_TOKEN and DATABRICKS_HTTP_PATH, as run.py does. Each step
adds its part to results/poc-databricks-workload.json.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run import ROOT, Databricks  # noqa: E402

RESULT = ROOT / "results" / "poc-databricks-workload.json"
SCHEMA = "workspace.dpa_bi"
QUERIES = ROOT / "baseline" / "analytics.sql"
MART_CONTRACT = ROOT / "models" / "contracts" / "usage-mart.odcs.yaml"
EVENTS_A_DAY = 350_000
DAYS = 90
FIRST = "TIMESTAMP '2026-07-02 00:00:00+00:00'"
# 90 days of microseconds over 31.5 million events, as integer arithmetic that cannot overflow.
STEP = f"(id * {DAYS * 86_400_000_000 // 10_000}) div {DAYS * EVENTS_A_DAY // 10_000}"
EVENT_TYPES = "'login', 'view_dashboard', 'view_dashboard', 'create_report', 'share_report', " \
              "'export_csv', 'invite_user', 'api_call'"  # fmt: skip


def events_select(first_id: int, last_id: int) -> str:
    """Events first_id..last_id - 1, one every 90 days / 31.5 million from 2 July, by
    deterministic hashes of the id (baseline/events.sql uses random(), seeded)."""
    return f"""
    SELECT id + 1 AS event_id, 1 + u % 6000 AS account_id, u AS user_id,
           element_at(array({EVENT_TYPES}), CAST(1 + pmod(xxhash64(id, 'type'), 8) AS INT)) AS event_type,
           element_at(array('web', 'web', 'web', 'ios', 'android'),
                      CAST(1 + pmod(xxhash64(id, 'platform'), 5) AS INT)) AS platform,
           t AS event_at, t + INTERVAL 30 SECONDS AS received_at
    FROM (SELECT id, 1 + pmod(xxhash64(id, 'user'), 60000) AS u,
                 timestamp_micros(unix_micros({FIRST}) + {STEP}) AS t
          FROM range({first_id}, {last_id}))"""


LOAD = [
    """CREATE OR REPLACE TABLE plans AS
       SELECT plan_id, plan_name, CAST(price AS DECIMAL(10, 2)) AS monthly_price_usd
       FROM VALUES (1, 'free', 0), (2, 'team', 49), (3, 'business', 199), (4, 'enterprise', 899)
            AS t(plan_id, plan_name, price)""",
    """CREATE OR REPLACE TABLE accounts AS
       SELECT id AS account_id, concat('Account ', id) AS account_name,
              concat('account', id, '.example') AS domain,
              element_at(array('software', 'retail', 'finance', 'health', 'media', 'education'),
                         CAST(1 + id % 6 AS INT)) AS industry,
              element_at(array('US', 'GB', 'DE', 'FR', 'NL', 'IN', 'AU', 'CA'),
                         CAST(1 + (id * 7) % 8 AS INT)) AS country,
              CASE WHEN r < 0.45 THEN 1 WHEN r < 0.80 THEN 2 WHEN r < 0.95 THEN 3 ELSE 4 END AS plan_id,
              CASE WHEN r2 < 0.97 THEN 'active' ELSE 'churned' END AS status,
              timestamp_seconds(s + CAST(r3 * (e - s) AS BIGINT)) AS signup_at,
              TIMESTAMP '2026-09-01 00:00:00+00:00' AS updated_at
       FROM (SELECT id, pmod(xxhash64(id, 'plan'), 1000000) / 1e6 AS r,
                    pmod(xxhash64(id, 'status'), 1000000) / 1e6 AS r2,
                    pmod(xxhash64(id, 'signup'), 1000000) / 1e6 AS r3,
                    unix_seconds(TIMESTAMP '2019-01-01 00:00:00+00:00') AS s,
                    unix_seconds(TIMESTAMP '2026-09-01 00:00:00+00:00') AS e
             FROM range(1, 6001))""",
    """CREATE OR REPLACE TABLE users AS
       SELECT id AS user_id, 1 + id % 6000 AS account_id,
              concat('user', id, '@account', 1 + id % 6000, '.example') AS email,
              concat('User ', id) AS full_name,
              element_at(array('admin', 'member', 'member', 'viewer'), CAST(1 + id % 4 AS INT)) AS role,
              timestampadd(DAY, id % 2700, TIMESTAMP '2019-01-01 00:00:00+00:00') AS created_at,
              CAST(NULL AS TIMESTAMP) AS last_seen_at
       FROM range(1, 60001)""",
    """CREATE OR REPLACE TABLE invoices AS
       SELECT row_number() OVER (ORDER BY a.account_id, m.m) AS invoice_id, a.account_id,
              m.m AS invoiced_at, p.monthly_price_usd AS amount_usd
       FROM accounts AS a
       JOIN plans AS p USING (plan_id)
       CROSS JOIN (SELECT explode(sequence(TIMESTAMP '2024-10-01 00:00:00+00:00',
                                           TIMESTAMP '2026-09-01 00:00:00+00:00',
                                           INTERVAL 1 MONTH)) AS m) AS m
       WHERE p.monthly_price_usd > 0 AND m.m >= date_trunc('MONTH', a.signup_at)""",
    f"CREATE OR REPLACE TABLE events AS {events_select(0, DAYS * EVENTS_A_DAY)}",
]


def mart_select(since: str | None = None) -> str:
    """fct_daily_usage as its contract defines it. The dataset has no plan changes, so each
    account has one dim_account version and its key is derived from the account alone."""
    where = f"WHERE e.event_at >= TIMESTAMP '{since} 00:00:00+00:00'" if since else ""
    return f"""
    SELECT to_date(e.event_at) AS activity_date, e.account_id,
           md5(concat_ws('|', a.account_id, a.updated_at)) AS account_key, a.plan_id,
           u.role AS user_role, e.event_type, COUNT(*) AS events,
           COUNT(DISTINCT e.user_id) AS active_users
    FROM events AS e
    JOIN users AS u ON u.user_id = e.user_id
    JOIN accounts AS a ON a.account_id = e.account_id
    {where}
    GROUP BY ALL"""


def daily_build() -> list[tuple[str, str]]:
    """30 September, with a two-day look-back (0008): loaded and replaced by window."""
    day, look_back = "2026-09-30", "2026-09-28"
    quality = yaml.safe_load(MART_CONTRACT.read_text())["schema"][0]["quality"][0]["query"]
    first = DAYS * EVENTS_A_DAY
    return [
        ("load_the_day", f"INSERT INTO events REPLACE WHERE event_at >= TIMESTAMP '{day} 00:00:00+00:00' "
                         f"{events_select(first, first + EVENTS_A_DAY)}"),
        ("replace_the_mart_window", f"INSERT INTO fct_daily_usage REPLACE WHERE activity_date >= "
                                    f"DATE '{look_back}' {mart_select(look_back)}"),
        ("contract_quality_check", quality),
    ]  # fmt: skip


def bi_queries() -> dict[str, str]:
    """baseline/analytics.sql, with Postgres's timestamptz literals written for Databricks."""
    queries, name = {}, None
    for line in QUERIES.read_text().splitlines():
        header = re.fullmatch(r"-- (\w+)", line.strip())
        if header:
            name = header.group(1)
            queries[name] = ""
        elif name:
            queries[name] += line + "\n"
    return {
        n: re.sub(r"timestamptz '([\d-]+) ([\d:]+)\+00'", r"TIMESTAMP '\1 \2:00+00:00'", q)
        .strip()
        .rstrip(";")
        for n, q in queries.items()
    }


def analysts(db: Databricks, count: int, rounds: int, tag: str) -> list[dict]:
    """`count` analysts at once, each on their own session, running the query set `rounds`
    times and starting at a different query. Each session has the result cache switched off
    (use_cached_result), so every query is executed; system.query.history confirms it. A
    comment alone does not do it: the cache ignores comments."""
    from databricks import sql as connector  # the poc dependency group

    queries = list(bi_queries().items())
    catalog, schema = SCHEMA.split(".")

    def analyst(a: int) -> list[dict]:
        log = []
        with connector.connect(server_hostname=db.host.removeprefix("https://"),
                               http_path=f"/sql/1.0/warehouses/{db.warehouse}", access_token=db.token,
                               catalog=catalog, schema=schema,
                               session_configuration={"use_cached_result": "false"}) as conn:  # fmt: skip
            with conn.cursor() as cursor:
                for r in range(rounds):
                    for i in range(len(queries)):
                        name, sql = queries[(a + r + i) % len(queries)]
                        started = time.perf_counter()
                        cursor.execute(f"{sql}\n/* {tag} analyst {a} round {r} */")
                        cursor.fetchall()
                        log.append({"query": name, "statement_id": cursor.query_id,
                                    "client_seconds": round(time.perf_counter() - started, 2)})  # fmt: skip
        return log

    with ThreadPoolExecutor(count) as pool:
        return [entry for log in pool.map(analyst, range(count)) for entry in log]


def history(db: Databricks, statement_ids: list[str], wait_minutes: int = 30) -> dict[str, dict]:
    """The warehouse's own record of each statement; the table fills a few minutes late."""
    ids = ", ".join(f"'{s}'" for s in statement_ids)
    columns = ("statement_id", "total_duration_ms", "waiting_for_compute_duration_ms",
               "waiting_at_capacity_duration_ms", "execution_duration_ms", "compilation_duration_ms",
               "from_result_cache", "read_rows", "read_bytes", "start_time", "end_time")  # fmt: skip
    deadline = time.time() + wait_minutes * 60
    while True:
        rows = db.sql(f"SELECT {', '.join(columns)} FROM system.query.history WHERE statement_id IN ({ids})")
        if len(rows) == len(statement_ids) or time.time() > deadline:
            break
        print(f"  query history: {len(rows)} of {len(statement_ids)} statements so far", flush=True)
        time.sleep(60)
    return {r[0]: dict(zip(columns[1:], r[1:], strict=True)) for r in rows}


def summarize(log: list[dict], seen: dict[str, dict]) -> dict:
    def ms(entry: dict, column: str) -> float:
        return int(seen[entry["statement_id"]][column] or 0) / 1000

    out: dict = {"queries": len(log), "in_history": sum(e["statement_id"] in seen for e in log)}
    found = [e for e in log if e["statement_id"] in seen]
    out["from_result_cache"] = sum(
        seen[e["statement_id"]]["from_result_cache"] in (True, "true") for e in found
    )
    out["by_query"] = {}
    for name in dict.fromkeys(e["query"] for e in found):
        mine = [e for e in found if e["query"] == name]
        total = sorted(ms(e, "total_duration_ms") for e in mine)
        out["by_query"][name] = {
            "runs": len(mine),
            "seconds_median": round(statistics.median(total), 2),
            "seconds_max": round(total[-1], 2),
            "executing_seconds_median": round(statistics.median(ms(e, "execution_duration_ms")
                                                                for e in mine), 2),
            "queued_seconds_max": round(max(ms(e, "waiting_at_capacity_duration_ms") for e in mine), 2),
            "rows_read_median": int(statistics.median(int(seen[e["statement_id"]]["read_rows"] or 0)
                                                      for e in mine)),
        }  # fmt: skip
    every = sorted(ms(e, "total_duration_ms") for e in found)
    out["seconds_median"] = round(statistics.median(every), 2)
    out["seconds_p95"] = round(every[min(len(every) - 1, int(0.95 * len(every)))], 2)
    out["queued_seconds_total"] = round(sum(ms(e, "waiting_at_capacity_duration_ms") for e in found), 1)
    return out


def postgres_medians() -> dict:
    """The same queries on Postgres at the brief's rate, on the primary: in the lab the
    replica shares the primary's disk, so the primary's timings are the clean ones
    (docs/02-current-state.md)."""
    log = json.loads((ROOT / "results" / "baseline-brief-rate.json").read_text())["bi_on_primary"]
    done = [e for e in log["bi_queries"]["log"] if e["outcome"] == "ok"]
    names = dict.fromkeys(e["query"] for e in done)
    return {n: statistics.median(e["seconds"] for e in done if e["query"] == n) for n in names}


def warehouse(db: Databricks) -> dict:
    w = db.api("GET", f"/api/2.0/sql/warehouses/{db.warehouse}")
    return {k: w.get(k) for k in ("cluster_size", "min_num_clusters", "max_num_clusters", "auto_stop_mins",
                                  "warehouse_type", "enable_serverless_compute", "state")}  # fmt: skip


def step_load(db: Databricks) -> dict:
    db.sql(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    took = {}
    for statement in [*LOAD, f"CREATE OR REPLACE TABLE fct_daily_usage AS {mart_select()}"]:
        name = re.search(r"TABLE (\w+)", statement).group(1)
        started = time.perf_counter()
        db.sql(statement, SCHEMA)
        took[name] = round(time.perf_counter() - started, 1)
        print(f"  {name}: {took[name]} s", flush=True)
    counts = {t: int(db.sql(f"SELECT COUNT(*) FROM {t}", SCHEMA)[0][0]) for t in took}
    first, last = db.sql("SELECT MIN(event_at), MAX(event_at) FROM events", SCHEMA)[0]
    return {"rows": counts, "seconds": took, "events_from": first, "events_to": last}


def step_speed(db: Databricks) -> dict:
    out: dict = {"warehouse": warehouse(db)}
    print("  warm-up: each query once", flush=True)
    warm = analysts(db, 1, 1, "warm-up")
    out["warm_up_client_seconds"] = {e["query"]: e["client_seconds"] for e in warm}
    runs = {}
    for count, rounds in ((2, 5), (8, 2)):
        print(f"  {count} analysts, {rounds} rounds each", flush=True)
        runs[count] = analysts(db, count, rounds, f"speed-{count}")
    seen = history(db, [e["statement_id"] for log in runs.values() for e in log])
    for count, log in runs.items():
        out[f"analysts_{count}"] = summarize(log, seen)
    out["postgres_on_the_primary_seconds_median"] = postgres_medians()
    return out


def wait_until_stopped(db: Databricks, limit_minutes: int = 40) -> str:
    deadline = time.time() + limit_minutes * 60
    while (state := warehouse(db)["state"]) != "STOPPED" and time.time() < deadline:
        time.sleep(30)
    return datetime.now(UTC).isoformat(timespec="seconds") if state == "STOPPED" else "did not stop"


def step_day(db: Databricks) -> dict:
    """One day's work on the warehouse, alone in a billing hour."""
    print("  waiting for the warehouse to stop", flush=True)
    wait_until_stopped(db)
    now = datetime.now(UTC)
    start = (now + timedelta(hours=1)).replace(minute=0, second=30, microsecond=0)
    print(f"  starting at {start:%H:%M:%S} UTC, alone in that billing hour", flush=True)
    time.sleep(max(0, (start - datetime.now(UTC)).total_seconds()))
    out: dict = {"warehouse": warehouse(db), "started": datetime.now(UTC).isoformat(timespec="seconds")}
    build = []
    for name, statement in daily_build():
        started = time.perf_counter()
        statement_id, rows = db.statement(statement, SCHEMA)
        build.append({"step": name, "statement_id": statement_id,
                      "client_seconds": round(time.perf_counter() - started, 2),
                      **({"duplicates": int(rows[0][0])}
                         if name == "contract_quality_check" else {})})  # fmt: skip
        print(f"  {name}: {build[-1]['client_seconds']} s", flush=True)
    out["build"] = build
    out["analysts"] = analysts(db, 2, 1, "day")
    out["last_statement"] = datetime.now(UTC).isoformat(timespec="seconds")
    print("  done; leaving the warehouse to stop itself", flush=True)
    out["stopped"] = wait_until_stopped(db)
    return out


def step_bill(db: Databricks, day: dict) -> dict:
    """Billed DBUs for the day's hour, against uptime and busy time."""
    started = datetime.fromisoformat(day["started"])
    hour = started.replace(minute=0, second=0, microsecond=0)
    until = datetime.fromisoformat(day["stopped"]).replace(minute=0, second=0, microsecond=0) + timedelta(
        hours=1
    )
    window = f"TIMESTAMP '{hour:%Y-%m-%d %H:%M:%S}+00:00' AND TIMESTAMP '{until:%Y-%m-%d %H:%M:%S}+00:00'"
    wid = db.warehouse
    billed = db.sql(f"""
        SELECT u.usage_start_time, u.usage_end_time, u.sku_name, u.usage_quantity,
               u.usage_quantity * p.pricing.default
        FROM system.billing.usage AS u
        LEFT JOIN system.billing.list_prices AS p
          ON p.sku_name = u.sku_name AND p.usage_unit = u.usage_unit
         AND u.usage_end_time >= p.price_start_time
         AND (p.price_end_time IS NULL OR u.usage_end_time < p.price_end_time)
        WHERE u.usage_metadata.warehouse_id = '{wid}' AND u.usage_start_time >= {window.split(" AND ")[0]}
          AND u.usage_end_time <= {window.split(" AND ")[1]}
        ORDER BY 1""")
    events = db.sql(f"""
        SELECT event_type, event_time FROM system.compute.warehouse_events
        WHERE warehouse_id = '{wid}' AND event_time BETWEEN {window} ORDER BY event_time""")
    up, running_since = 0.0, None
    for kind, at in events:
        t = datetime.fromisoformat(at.replace("Z", "+00:00"))
        if kind == "STARTING" and running_since is None:
            running_since = t
        elif kind == "STOPPED" and running_since is not None:
            up += (t - running_since).total_seconds()
            running_since = None
    ids = [b["statement_id"] for b in day["build"]] + [a["statement_id"] for a in day["analysts"]]
    seen = history(db, ids)

    def at(text: str) -> datetime:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))

    spans = sorted((at(s["start_time"]), at(s["end_time"])) for s in seen.values())
    busy, edge = 0.0, None
    for s, e in spans:  # the union of the statements' intervals
        if edge is None or s > edge:
            busy += (e - s).total_seconds()
            edge = e
        elif e > edge:
            busy += (e - edge).total_seconds()
            edge = e
    dbu = sum(float(r[3]) for r in billed)
    rate = 4  # DBU an hour, a 2X-Small serverless SQL warehouse
    return {
        "billed_rows": [[r[0], r[1], r[2], round(float(r[3]), 4)] for r in billed],
        "dbu": round(dbu, 3),
        "usd_at_list_price": round(sum(float(r[4] or 0) for r in billed), 2),
        "warehouse_events": events,
        "uptime_minutes": round(up / 60, 1),
        "busy_minutes": round(busy / 60, 2),
        "dbu_for_the_uptime_at_4_an_hour": round(up / 3600 * rate, 3),
        "build_executing_seconds": round(
            sum(
                int(seen[b["statement_id"]]["execution_duration_ms"] or 0)
                for b in day["build"]
                if b["statement_id"] in seen
            )
            / 1000,
            1,
        ),  # fmt: skip
        "share_of_uptime_idle": round(1 - busy / up, 3) if up else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("steps", nargs="+", choices=("load", "speed", "compare", "day", "bill"))
    args = ap.parse_args()
    result = json.loads(RESULT.read_text()) if RESULT.exists() else {}
    db = None
    if set(args.steps) - {"compare"}:  # compare reads local results only
        db = Databricks()
        result["databricks_sql"] = db.sql("SELECT current_version().dbsql_version")[0][0]
    for step in args.steps:
        print(step, flush=True)
        if step == "bill":
            result["bill"] = step_bill(db, result["day"])
        elif step == "compare":
            result["speed"].pop("postgres_replica_seconds_median", None)
            result["speed"]["postgres_on_the_primary_seconds_median"] = postgres_medians()
        else:
            result[step] = {"load": step_load, "speed": step_speed, "day": step_day}[step](db)
        RESULT.write_text(json.dumps(result, indent=2, default=str) + "\n")
        print(json.dumps(result.get(step, result.get("speed")), default=str)[:1500], flush=True)
    print(f"wrote {RESULT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
