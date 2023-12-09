=============
Update states
=============

Once submitted to Bodhi, updates move through the following states:

:ref:`pending`: The update has not yet been pushed to the testing or stable repositories.

:ref:`pending-testing`: The package is ready to go testing, and will wait until the next update push.

:ref:`testing`: The package is in the updates-testing repository for people to test.

:ref:`testing-stable`: The package is ready to go stable, and will wait until the next update push.

:ref:`stable`: The package has been released to the main updates repository.

:ref:`obsolete`: The package has been obsoleted by a different update

:ref:`unpushed`: The update has been removed from testing.

.. note:: | In the case of Fedora rawhide, the states described here are a little bit changed
           as rawhide has only two states (testing, stable).
          | For rawhide, ``Testing`` means that the update is being tested by the automatic test
           systems (ie: CI (continuous integration) tests are running), and ``Stable`` means
           that the builds of the update are available in the buildroot.
          | **Unlike** stable branches, it does not mean that the builds of the update are
           available for anyone to download on the master mirror.

.. _pending:

Pending
=======

Once an update is submitted to Bodhi it will enter the pending state. Bodhi will perform some sanity
checks on the update request. Is the package built and available in koji? Is it tagged as an updates
candidate for the release it is intended for? The update path for the package will also be checked
at this point to make sure you don't release a newer version of a package on an older release. The
update must not break the upgrade path or it will be rejected.

Bodhi will send e-mail notifications when the update has been signed and pushed.


.. _pending-testing:

Pending/Testing
===============

The update is ready to be pushed into the testing repositories, which will happen at the next
compose run.


.. _testing:

Testing
=======

The testing status means that the update has been pushed to its release's testing repository. While
in the testing repository users may provide feedback via karma and comments. Once enough feedback is
generated, Bodhi's web interface can be used to release the update by clicking
'Mark as Stable', or it can be removed by using 'Unpush'. The command line interface can
also be used to perform these actions.

If the update is configured to use the 'autokarma', it will automatically be pushed or unpushed based
on the feedback from testers. This feature can be disabled if you wish to push your update to the
stable repository only manually. By default, if your update achieves a karma of 3, it will
automatically be pushed to stable, and will be unpushed if it reaches -3.

Also, the 'autotime' setting can be enabled, so that the update will be automatically pushed to stable
after spending a certain amount of time in testing repositories, even if it has not reached a minimum
karma. On the other hand, if any user submits negative karma, the 'autotime' feature will be disabled.


.. _testing-stable:

Testing/Stable
==============

The update is ready to be pushed into the stable repositories, which will happen at the next
compose run. The update will remain in the testing repository during this state.


.. _stable:

Stable
======

After an update is pushed to the stable repository, it is marked as stable in Bodhi. At this point,
Bodhi will close associated bugs, and will send out update notices to the appropriate e-mail
addresses.


.. _obsolete:

Obsolete
========

When submitting a new version of a package, Bodhi will automatically obsolete any pending or testing
updates that do not have an active push request. Once obsoleted, the new update will inherit the old
update's bugs and notes.


.. _unpushed:

Unpushed
========

The developer has decided to pull the update from the testing repository. This state can only be
reached if the update is in the testing state.


Revoking push requests
======================

When an update is moving from pending to testing or from testing to stable, the developer can revoke
the push request either from the webUI or from CLI with the 'revoke' command.

Revoking a testing request will set the update to the Unpushed state. The developer can then
re-submit the update to testing and restart the update flow.

Revoking a stable request will cause the update to remain in the testing repositories and not be
pushed to stable at the next compose. Be aware if any of 'autokarma' or 'autotime' are enabled,
the update will automatically be resubmitted to stable after a short amount of time. To prevent that
the developer has to edit the update and disable those automatisms.


Frozen updates
==============

A package is said to be in a frozen state when a release is stabilized before the release Beta or
GA (Generaly Available). In such a state, all updates are blocked and release engineering will only
push the updates that have been given a freeze break exception to fix a bug.
