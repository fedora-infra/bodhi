set -m

# Bodhi backend
echo "Starting Fedora Messaging consumers"
fedora-messaging consume &

# Celery
echo "Starting Celery"
pushd /  # Otherwise celeryconfig will be picked up from CWD (/bodhi)
PYTHONPATH=/etc/bodhi celery-3 worker -A bodhi.server.tasks.app -Q celery,has_koji_mount -l debug &
popd

echo "Starting Bodhi"
# Bodhi webserver
mkdir /httpdir/run
ln -s /etc/httpd/modules /httpdir/modules
truncate --size=0 /httpdir/accesslog /httpdir/errorlog
tail -qf /httpdir/accesslog /httpdir/errorlog &
httpd -f /etc/bodhi/httpd.conf -DFOREGROUND -DNO_DETACH
