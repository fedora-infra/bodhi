#!/bin/bash
set -e

psql -U postgres -c "CREATE USER waiverdb CREATEDB;"
psql -U postgres -c "CREATE USER bodhi2 CREATEDB;"
psql -U postgres -c "CREATE DATABASE bodhi2;"
xzcat /docker-entrypoint-initdb.d/waiverdb.dump.xz | psql -U postgres
xzcat /docker-entrypoint-initdb.d/bodhi2.dump.xz | psql bodhi2 -U postgres
touch /tmp/.init-done
