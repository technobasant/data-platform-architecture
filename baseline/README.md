# The current state, measured

A lab copy of the client's database, used for [2. Current state](../docs/02-current-state.md):
a Postgres 17 primary and a streaming read replica, each limited to 2 vCPU and 4 GB, with
the product's tables at the brief's scale (6,000 accounts, 60,000 users, 90 days of events:
31.5 million rows, 5 GB with indexes), all seeded so every run builds the same data.

| File | What it is |
|---|---|
| [`compose.yml`](compose.yml) | the primary, the replica, and a client container for pgbench |
| [`schema.sql`](schema.sql), [`load.sql`](load.sql), [`events.sql`](events.sql) | the product's tables and the seeded data; events in arrival order, as the product appends them |
| [`app.sql`](app.sql) | one product request: a customer's usage page, an activity update and an event insert |
| [`analytics.sql`](analytics.sql) | the four queries the BI tool runs |
| [`run.py`](run.py) | the four scenarios, and `results/baseline.json` |

## Running it

```bash
cd baseline
docker compose up -d primary
docker compose exec -T primary psql -U postgres -q -f /baseline/schema.sql
docker compose exec -T primary psql -U postgres -f /baseline/load.sql      # about 5 minutes
cd ..
uv sync --group baseline
uv run python baseline/run.py                                               # about 30 minutes
```

`run.py` starts the replica, then runs a two-minute warm-up and four five-minute scenarios.
Before each it forces a checkpoint and waits for the replica to replay it, so every scenario
starts from the same state; the primary's checkpoint interval is 30 minutes so none falls
inside a scenario. The product's requests run at 100 a second from eight connections, about
half what the lab primary can serve. Two analyst sessions run the BI queries in turn.

If the primary is reloaded, the replica must be cloned again:
`RECLONE=1 docker compose up -d replica`, then `docker compose up -d replica` once it streams.

## Limits

Docker Desktop on a laptop, not RDS: absolute latencies, especially the slowest 1%, include
the virtual disk's flush times and are higher than RDS would show. The comparison between
scenarios on the same machine is the result; the absolute numbers are not. Everything runs
on local trust authentication, bound to localhost.
