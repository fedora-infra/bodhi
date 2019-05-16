#
# Celery configuration file
# See: docs.celeryproject.org/en/latest/userguide/configuration.html
#

# Broker URL
# This might be more appropriate in prod:
# broker_url = amqps://user:password@hostname:port//vhost
# broker_use_ssl =
#   keyfile=/var/ssl/private/worker-key.pem
#   certfile=/var/ssl/amqp-server-cert.pem
#   ca_certs=/var/ssl/myca.pem
#   cert_reqs=ssl.CERT_REQUIRED
broker_url = "amqp://localhost/"

# Where the tasks are defined
imports = "bodhi.server.tasks"

# Task routing
task_routes = {
    # Route the compose task to a specific queue that will only be run on hosts
    # that have a Koji mount.
    'compose': {'queue': 'has_koji_mount'},
}
