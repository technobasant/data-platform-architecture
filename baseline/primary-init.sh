#!/bin/bash
# Allow the replica to stream WAL from the primary.
set -e
echo "host replication all all trust" >> "$PGDATA/pg_hba.conf"
