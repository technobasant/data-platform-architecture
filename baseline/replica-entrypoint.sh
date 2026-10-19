#!/bin/bash
# Clone the primary once (again if RECLONE=1, after the primary was reloaded), then run
# as a hot standby. FEEDBACK sets hot_standby_feedback.
set -e
PGDATA=/var/lib/postgresql/data
mkdir -p "$PGDATA" && chown postgres "$PGDATA" && chmod 700 "$PGDATA"
until gosu postgres pg_isready -h primary -U postgres -q; do sleep 1; done
if [ ! -f "$PGDATA/standby.signal" ] || [ "${RECLONE:-0}" = "1" ]; then
  gosu postgres bash -c "rm -rf '$PGDATA'/* && pg_basebackup -h primary -U postgres -D '$PGDATA' -R -X stream -c fast"
fi
exec gosu postgres postgres -c shared_buffers=1GB -c work_mem=64MB -c hot_standby=on \
  -c hot_standby_feedback="${FEEDBACK:-off}" -c max_standby_streaming_delay=30s
