==============
Administration
==============


System Requirements
===================

Bodhi is currently only supported on active Fedora releases. It requires PostgreSQL >= 9.2.0.


Configuration
=============

The Bodhi server is configured via an INI file found at ``/etc/bodhi/production.ini``. Bodhi ships
an example ``production.ini`` file that has all settings documented. Most settings have reasonable
defaults if not defined, and the example settings file describes the default values in the
commented settings. Here is a copy of the example config file with in-line documentation:

.. include:: ../production.ini
   :literal:


Logging
-------

The example configuration above includes an example default logging configuration. However, you may
wish to do something more advanced, such as e-mail error messages to an address with rate limiting.
Bodhi provides a rate limiting Python logging Filter at ```bodhi.server.logging.RateLimiter```.

Unfortunately, it is not possible to use Python logging filters with Pyramid's ini file, so if you
wish to use Bodhi's ```RateLimiter``` log filter, you will need to configure Pyramid to use
`pyramid_sawing`_ so that it can use more advanced logging configuration. As a quick example, you
might put something like this into ``/etc/bodhi/production.ini`` to configure Pyramid to use
```pyramid_sawing``` and to look for a logging config at ```/etc/bodhi/logging.yaml```::

    pyramid.includes =
        pyramid_sawing
    pyramid_sawing.file = /etc/bodhi/logging.yaml

Then you could configure all of you logging in ```/etc/bodhi/logging.yaml```. Here is a snippet you
could use in that file to get Bodhi to e-mail error logs, but to limit them to one e-mail per hour
per process per spot in the code that logs errors::

    ---
    version: 1

    formatters:
      generic:
        format: '%(asctime)s %(levelname)-5.5s [%(name)s][%(threadName)s] %(message)s'
    filters:
      rate_limit:
        (): bodhi.server.logging.RateLimiter
        rate: 3600
    handlers:
      smtp:
        class: logging.handlers.SMTPHandler
        mailhost: "smtp.example.com"
        fromaddr: "bodhi@example.com"
        toaddrs:
            - "admin@example.com"
        subject: "Bodhi had a sad"
        level: ERROR
        formatter: generic
        filters: [rate_limit]
    loggers:
      bodhi:
        level: INFO
        handlers: [smtp]
        propagate: 0
    root:
      level: NOTSET
      handlers: []


You can read more detail about the ```RateLimiter``` below:

.. autoclass:: bodhi.server.logging.RateLimiter
   :members:


.. _pyramid_sawing: https://pypi.org/project/pyramid_sawing/


Components
==========

CLI tools
---------

See the :doc:`user/man_pages/index` documentation for a list of CLI tools that come with Bodhi.


Web Server
----------

Bodhi has a web server component that runs its REST API and serves the web interface.


Message Consumers
-----------------

The following sections document the list of messaging consumers.


Automatic updates
^^^^^^^^^^^^^^^^^

This consumer will create updates automatically when builds are tagged to a Release's candidate tag,
if the Release associated with that tag is configured to do so by having its
``create_automatic_updates`` boolean set to True.


Composer
^^^^^^^^

Bodhi has a process called the "composer" that is responsible for generating the repositories that
move packages along the path to their destiny. For each release, there are two composes that get
run, one for the release's testing repository, and the other for the release's stable repository.

Administrators can use the ``bodhi-push`` tool to start composes. To view the status of composes
once they have been started, users can use ``bodhi composes list`` or they can visit the
``/composes/`` URL on the server. Composes can be in the following states:

* **requested**: The compose has been created by ``bodhi-push``, but the composer has not yet
  started working on the task.
* **pending**: The composer has received the task and will start it when it has free threads to do
  so.
* **initializing**: The composer has started working on the task.
* **updateinfo**: The composer is generating the ``updateinfo.xml`` file.
* **punging**: The composer is waiting for Pungi to finish creating the
  repository.
* **syncing_repo**: The composer is polling the master mirror and waiting until the newly composed
  repository is present there.
* **notifying**: The composer is sending out notifications about the updates.
* **success**: The composer has successfully finished the task. This state does not last long as
  the records of successful composes are deleted shortly after reaching this state.
* **failed**: The composer has failed. An administrator will usually have to inspect the error
  message associated with the compose to determine what action to take to correct the problem, and
  then the compose can be resumed with ``bodhi-push``.
* **signing_repo**: The composer is waiting on the repository to be signed.
* **cleaning**: The composer is cleaning up old composes. This state only occurs if
  ``clean_old_composes`` is set to True in the settings.


Greenwave Handler
^^^^^^^^^^^^^^^^^

Bodhi's greenwave handler watches for messages sent from greenwave about bodhi updates that have
been tested. When a message is recieved, the appropriate update is updated with the greenwave test
status.


Signed Handler
^^^^^^^^^^^^^^

Bodhi's signed handler is responsible for watching for messages from Robosignatory when it signs
builds, and marking those builds as signed in the Bodhi database.


Update Handler
^^^^^^^^^^^^^^

Bodhi's update handler watches for messages sent from the web server when updates are created or
edited. When it sees these messages, it does background tasks, such as querying bugzilla to
determine the titles on associated tickets, or querying the Wiki to retrieve test case information.
