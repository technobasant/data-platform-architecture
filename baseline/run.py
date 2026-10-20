"""Measure the company's current state: the product and its BI queries on one Postgres.

A primary and a streaming replica (2 vCPU, 4 GB each) hold the product's tables at the
brief's scale. pgbench runs the product's request (`app.sql`: a customer's usage page,
an activity update, an event insert) at a fixed rate, from its own container. Two
analyst sessions loop over the BI queries (`analytics.sql`). Five scenarios:

  app_alone            the product only
  bi_on_primary        BI queries on the primary, as when the replica is down or new
  bi_on_replica        BI queries on the replica, hot_standby_feedback off (the default)
  bi_on_replica_fb     the same with hot_standby_feedback on
  bi_on_replica_delay  a replica for BI alone: feedback off, max_standby_streaming_delay
                       raised from 30 s to 15 minutes, so replay waits for reports instead of
                       cancelling them, and the replica falls behind instead

Recorded per scenario: the product's latency (p50, p95, p99 from pgbench's per-request
log), each BI query's duration and outcome, recovery conflicts on the replica, its replay
lag, and dead rows and size of the `users` table on the primary.

    docker compose up -d primary            # then load once: see README.md
    python baseline/run.py --rate 12 --out results/baseline-brief-rate.json   # about 30 minutes
    python baseline/run.py --rate 100       # the stress run in results/baseline.json

Each request records one event, so the rate is events a second: 12 is about three times the
brief's daily average of 4 (350,000 a day), a weekday peak. 100 is a stress rate, about 25
times the average, at which the first results were recorded.

Timings depend on the host; they are observations, recorded and not compared in CI.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import threading
import time
from pathlib import Path

import psycopg

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "out"
RESULT = ROOT / "results" / "baseline.json"
PRIMARY = "host=127.0.0.1 port=55432 user=postgres dbname=postgres"
REPLICA = "host=127.0.0.1 port=55433 user=postgres dbname=postgres"
CLIENTS, ANALYSTS = 8, 2  # pgbench connections; analysts running reports
DELAY = "900s"  # max_standby_streaming_delay of the BI-only replica in bi_on_replica_delay


def compose(*args: str, env: dict | None = None) -> None:
    subprocess.run(["docker", "compose", *args], cwd=HERE, check=True,
                   env={**os.environ, **(env or {})}, capture_output=True)  # fmt: skip


def queries() -> list[tuple[str, str]]:
    """(name, sql) pairs from analytics.sql, split on '-- name' lines."""
    out, name, lines = [], None, []
    for line in (HERE / "analytics.sql").read_text().splitlines():
        stripped = line.removeprefix("-- ").strip()
        if line.startswith("-- ") and stripped.replace("_", "").isalnum() and stripped.islower():
            if name:
                out.append((name, "\n".join(lines).strip().rstrip(";")))
            name, lines = stripped, []
        elif name:
            lines.append(line)
    out.append((name, "\n".join(lines).strip().rstrip(";")))
    return out


def wait_ready(dsn: str, timeout: int = 600) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(dsn, connect_timeout=3) as c:
                c.execute("select 1")
                return
        except psycopg.OperationalError:
            time.sleep(2)
    raise SystemExit(f"not ready: {dsn}")


def one(dsn: str, sql: str):
    with psycopg.connect(dsn, autocommit=True) as c:
        return c.execute(sql).fetchone()


def users_table() -> dict:
    dead, live, size = one(PRIMARY, "select n_dead_tup, n_live_tup, pg_relation_size('users') "
                                    "from pg_stat_user_tables where relname = 'users'")  # fmt: skip
    return {"dead_rows": dead, "live_rows": live, "size_kb": size // 1024}


def analyst(dsn: str, order: list[tuple[str, str]], deadline: float, log: list) -> None:
    """Run the BI queries in turn until the deadline; record each one's outcome."""
    i = 0
    while time.monotonic() < deadline:
        name, sql = order[i % len(order)]
        i += 1
        started = time.monotonic()
        try:
            with psycopg.connect(dsn, autocommit=True) as c:
                c.execute(sql).fetchall()
            outcome = "ok"
        except psycopg.Error as e:
            outcome = e.sqlstate or type(e).__name__
        log.append({"query": name, "seconds": round(time.monotonic() - started, 1),
                    "outcome": outcome})  # fmt: skip


def lag_sampler(deadline: float, samples: list) -> None:
    while time.monotonic() < deadline:
        try:
            lag = one(REPLICA, "select coalesce(extract(epoch from now() - "
                               "pg_last_xact_replay_timestamp()), 0)")[0]  # fmt: skip
            samples.append(float(lag))
        except psycopg.Error:
            pass
        time.sleep(5)


def latencies(prefix: str) -> dict:
    """Per-request latency from pgbench's log, in ms. At a fixed rate the logged time runs
    from the request's scheduled start, so it includes any wait to begin."""
    ms = []
    for path in OUT.glob(f"{prefix}.*"):
        for line in path.read_text().split("\n"):
            parts = line.split()
            if len(parts) >= 7:
                ms.append(int(parts[2]) / 1000)
    ms.sort()

    def pct(p: float) -> float:
        return round(ms[min(len(ms) - 1, int(p * len(ms)))], 1)

    return {"requests": len(ms), "p50_ms": pct(0.50), "p95_ms": pct(0.95), "p99_ms": pct(0.99),
            "max_ms": round(ms[-1], 1), "mean_ms": round(statistics.fmean(ms), 1),
            "over_100ms_pct": round(100 * sum(m > 100 for m in ms) / len(ms), 2)}  # fmt: skip


def settle() -> None:
    """Start every scenario alike: a checkpoint, and the replica caught up with it."""
    with psycopg.connect(PRIMARY, autocommit=True) as c:
        c.execute("checkpoint")
    target = one(PRIMARY, "select pg_current_wal_lsn()")[0]
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        if one(REPLICA, f"select pg_last_wal_replay_lsn() >= '{target}'::pg_lsn")[0]:
            return
        time.sleep(2)
    raise SystemExit("the replica did not catch up")


def conflicts() -> int:
    return one(REPLICA, "select confl_snapshot + confl_lock + confl_bufferpin + confl_deadlock "
                        "from pg_stat_database_conflicts where datname = 'postgres'")[0]  # fmt: skip


def scenario(name: str, seconds: int, bi_dsn: str | None, rate: int) -> dict:
    for old in OUT.glob(f"{name}.*"):
        old.unlink()
    settle()
    before_users = users_table()
    before_conflicts = conflicts()
    deadline = time.monotonic() + seconds
    bi_log: list = []
    lags: list = []
    threads = []
    if bi_dsn:
        qs = queries()
        for a in range(ANALYSTS):  # each analyst starts at a different query
            order = qs[a * 2 :] + qs[: a * 2]
            threads.append(threading.Thread(target=analyst, args=(bi_dsn, order, deadline, bi_log)))
    threads.append(threading.Thread(target=lag_sampler, args=(deadline, lags)))
    for t in threads:
        t.start()
    subprocess.run(
        ["docker", "compose", "run", "--rm", "client", "pgbench", "-h", "primary", "-U", "postgres",
         "-n", "-f", "/baseline/app.sql", "-c", str(CLIENTS), "-j", "2", "-R", str(rate),
         "-T", str(seconds), "-l", f"--log-prefix=/out/{name}", "postgres"],
        cwd=HERE, check=True, capture_output=True,
    )  # fmt: skip
    for t in threads:
        t.join()
    after_users = users_table()
    long_queries = [q for q in bi_log if q["query"] != "revenue_by_plan_month"]
    result = {
        "seconds": seconds,
        "app": latencies(name),
        "bi_queries": {
            "run": len(bi_log),
            "completed": sum(q["outcome"] == "ok" for q in bi_log),
            "cancelled_by_recovery_conflict": sum(q["outcome"] == "40001" for q in bi_log),
            "long_queries_completed": sum(q["outcome"] == "ok" for q in long_queries),
            "long_queries_run": len(long_queries),
            "log": bi_log,
        },
        "replica": {
            "recovery_conflicts": conflicts() - before_conflicts,
            "replay_lag_max_s": round(max(lags, default=0.0), 1),
            "replay_lag_median_s": round(statistics.median(lags), 1) if lags else 0.0,
        },
        "users_table": {"before": before_users, "after": after_users},
    }
    print(f"{name}: app p50 {result['app']['p50_ms']} ms, p95 {result['app']['p95_ms']} ms, "
          f"p99 {result['app']['p99_ms']} ms, over 100 ms {result['app']['over_100ms_pct']}%; "
          f"BI {result['bi_queries']['completed']}/{result['bi_queries']['run']} completed, "
          f"{result['bi_queries']['cancelled_by_recovery_conflict']} cancelled; lag max "
          f"{result['replica']['replay_lag_max_s']} s; users dead rows "
          f"{before_users['dead_rows']} -> {after_users['dead_rows']}", flush=True)  # fmt: skip
    return result


def replica(feedback: str, delay: str = "30s") -> None:
    compose("up", "-d", "replica", env={"FEEDBACK": feedback, "DELAY": delay})
    wait_ready(REPLICA)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=300, help="length of each scenario")
    ap.add_argument("--rate", type=int, default=100, help="product requests (events) a second")
    ap.add_argument("--out", type=Path, default=RESULT)
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    wait_ready(PRIMARY)
    if not one(PRIMARY, "select to_regclass('loaded_marker') is not null")[0]:
        raise SystemExit("load the data first: see baseline/README.md")
    replica("off")
    version = one(PRIMARY, "select current_setting('server_version')")[0]
    out = {"postgres": version, "rate_per_s": args.rate, "clients": CLIENTS, "analysts": ANALYSTS}
    scenario("warmup", 120, None, args.rate)
    out["app_alone"] = scenario("app_alone", args.seconds, None, args.rate)
    out["bi_on_primary"] = scenario("bi_on_primary", args.seconds, PRIMARY, args.rate)
    out["bi_on_replica"] = scenario("bi_on_replica", args.seconds, REPLICA, args.rate)
    replica("on")
    out["bi_on_replica_fb"] = scenario("bi_on_replica_fb", args.seconds, REPLICA, args.rate)
    if args.out != RESULT:  # the stress run predates this scenario
        replica("off", DELAY)
        out["bi_on_replica_delay"] = scenario("bi_on_replica_delay", args.seconds, REPLICA, args.rate)
        out["bi_on_replica_delay"]["max_standby_streaming_delay"] = DELAY
    replica("off")
    path = args.out if args.out.is_absolute() else ROOT / args.out
    path.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
