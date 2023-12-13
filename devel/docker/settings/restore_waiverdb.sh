#!/bin/bash
set -e

psql -U postgres -c "CREATE USER waiverdb CREATEDB;"
psql -U postgres -f /docker-entrypoint-initdb.d/wdb_pgdata
