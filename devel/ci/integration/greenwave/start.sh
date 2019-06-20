set -m

fedora-messaging consume &

gunicorn-3 --workers 8 --bind 0.0.0.0:8080 --access-logfile=- --error-logfile=- --enable-stdio-inheritance greenwave.wsgi:app

