"""Constants for Bodhi CI."""

import multiprocessing
import os
import uuid


CONTAINER_NAME = 'bodhi-ci'
# We label the containers we run so it's easy to find them when we run _stop_all_jobs() at the end.
# UUID is used so that one bodhi-ci process does not stop jobs started by a different one.
CONTAINER_LABEL = 'purpose=bodhi-ci-{}'.format(uuid.uuid4())
# This template is used to generate the summary lines that are printed out at the end.
LABEL_TEMPLATE = '{:>8}-{:<34}'
PROJECT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
DEFAULT_OPTIONS = dict(
    # concurrency: The number of Jobs we will run in parallel.
    concurrency=multiprocessing.cpu_count(),
    container_runtime='docker',
    failfast=False,
    only_tests=None,
    init=True,
    # If True, we will try to skip running any builds if suitable builds already exist.
    no_build=False,
    tty=False,
    z=False,
    # archive: Whether to set up an archive volume to mount in the container.
    archive=True,
    # archive_path: Which path on the host so share into the container when archive is True.
    archive_path=os.path.join(PROJECT_PATH, 'test_results'),
    # buffer_output: If True, this Job will buffer its stdout and stderr into its output property.
    # If False, child processes will send their output straight to stdout and stderr.
    buffer_output=True,
)

RELEASES = ('f34', 'f35', 'f36', 'rawhide', 'pip')
INTEGRATION_APPS = ("resultsdb", "waiverdb", "greenwave", "rabbitmq", "ipsilon")
MODULES = ("bodhi-client", "bodhi-messages", "bodhi-server")
