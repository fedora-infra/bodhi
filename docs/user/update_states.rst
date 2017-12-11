=============
Update states
=============

Once submitted to Bodhi, updates move through the following states:

:ref:`pending`: The update has not yet been pushed to the testing or stable repositories.

:ref:`testing`: The package is in the updates-testing repository for people to test.

:ref:`testing-batched`: The package is ready to go stable, and will wait until the next batched
update push to be marked for stable.

:ref:`testing-stable`: The package is ready to go stable, and will wait until the next update push.

:ref:`stable`: The package has been released to the main updates repository.

:ref:`obsolete`: The package has been obsoleted by a different update

:ref:`revoked`: The update was removed before it reached the testing repository.

:ref:`unpushed`: The update has been removed from testing.


.. _pending:

Pending
=======

Once an update is submitted to Bodhi it will enter the pending state. Bodhi will perform some sanity
checks on the update request. Is the package built and available in koji? Is it tagged as an updates
candidate for the release it is intended for? The update path for the package will also be checked
at this point to make sure you don't release a newer version of a package on an older release. The
update must not break the upgrade path or it will be rejected.

Bodhi will send e-mail notifications when the update has been signed and pushed.


.. _testing:

Testing
=======

The testing status means that the update has been pushed to its release's testing repository. While
in the testing repository users may provide feedback via karma and comments. Once enough feedback is
generated, Bodhi's web interface can be used to release the update by clicking
'Mark as Batched/Stable', or it can be removed by using 'Delete'. The command line interface can
also be used to perform these actions.

If the update is configured to use the 'autopush', it will automatically be pushed or unpushed based
on the feedback from testers. This feature can be disabled if you wish to push your update to the
stable repository manually. By default, if your update achieves a karma of 3, it will automatically
be pushed to stable, and will be unpushed if it reaches -3.

Testing also has two possible substates, both expressed as the "request", that occur when your
package is ready to go to stable. These are documented in the next two sections.


.. _testing-batched:

Testing/Batched
===============

The "batched" state means that the package is ready to go to stable and is waiting until the next
batched update when Bodhi will switch the request to "stable". All non-urgent and non-newpackage
updates will automatically move to this state when they hit the karma threshold if they have
autokarma enabled, and non-autokarma updates that meet the requirements will present a
"Push to Batched" button to the maintainers. The update remains in the testing repository while it
is in this state.


.. _testing-stable:

Testing/Stable
==============

The second request state is "stable", and means that the package will be sent out to the stable
repositories the next time a Release Engineer runs the update push command. The update will remain
in the testing repository during this state.

Developers are encouraged to use the batched update state for updates that are not severe as it
reduces the update churn for end users and also improves the speed of most of Bodhi's pushes (except
for the larger batched pushes, of course). However, it remains the maintainer's option to choose
when they use the "Push to Stable" button, which will remain available to them.


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


.. _revoked:

Revoked
=======

The update was withdrawn before it reached the testing repository.


.. _unpushed:

Unpushed
========

The developer has decided to pull the update from the testing respository. This state can only be
reached if the update is in the testing state.
