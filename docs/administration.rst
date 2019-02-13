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


Composes
========

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
