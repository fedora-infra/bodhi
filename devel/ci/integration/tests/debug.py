"""
Used to debug the integration tests. Just run::

    $ export BODHI_INTEGRATION_IMAGE=bodhi-ci-integration-bodhi/f35
    $ pytest --no-cov -s ./devel/ci/integration/tests/debug.py

and the integration tests will setup the containers and open a shell for you to debug.
You can list running containers with ``docker ps``, they should be properly named.
Then call ``docker exec -it <app> /bin/bash`` to enter the container you need to debug.
Exit the shell when you're done.
"""

from subprocess import run


def test_debug(bodhi_container, ipsilon_container):
    print(
        "OK you can now debug the integration testing environment. "
        "Exit the shell when you're done."
    )
    run(["bash"])
