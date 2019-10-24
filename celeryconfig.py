#
# Celery configuration file
# See: docs.celeryproject.org/en/latest/userguide/configuration.html
#

from celery.schedules import crontab


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

# Results
result_backend = 'rpc://'
result_persistent = True

# Task routing
task_routes = {
    # Route the following tasks to a specific queue that will only be run on
    # hosts that have a Koji mount.
    'compose': {'queue': 'has_koji_mount'},
    'clean_old_composes': {'queue': 'has_koji_mount'},
}


# Periodic tasks

beat_schedule = {
    "approve-testing": {
        "task": "bodhi.server.tasks.approve_testing_task",
        "schedule": 3 * 60,  # every 3 minutes
    },
    "check-policies": {
        "task": "bodhi.server.tasks.check_policies_task",
        "schedule": 60 * 60,  # every hour
    },
    "clean-old-composes": {
        "task": "bodhi.server.tasks.clean_old_composes_task",
        "schedule": crontab(hour=3, minute=3),
        "kwargs": {"num_to_keep": 10},
    },
    "expire-overrides": {
        "task": "bodhi.server.tasks.expire_overrides_task",
        "schedule": 60 * 60,  # every hour
    },
}
