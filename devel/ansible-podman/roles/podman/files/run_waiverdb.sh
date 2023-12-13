#!/bin/sh
. /venv/bin/activate
waiverdb wait-for-db && waiverdb db upgrade && gunicorn --bind 0.0.0.0:6544 --access-logfile=- --enable-stdio-inheritance waiverdb.wsgi:app
