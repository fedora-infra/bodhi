=============
Update states
=============

Once submitted to Bodhi, updates move through the following states:

:ref:`pending`: The update has not yet been pushed to the testing or stable repositories.

:ref:`testing`: The package is in the updates-testing repository for people to test.

:ref:`testing-stable`: The package is ready to go stable, and will wait until the next update push.

:ref:`stable`: The package has been released to the main updates repository.

:ref:`sidetag-active`: This update represents a side tag whose content can still be modified; i.e. in which packages can still be built.

:ref:`sidetag-active-testing`: This update represents a side tag that has been requested to merge for testing.

:ref:`sidetag-active-stable`: This update represents a side tag that has been requested to go stable.

:ref:`sidetag-expired`: This update represents a side tag whose lifetime has expired and can no longer be modified.

:ref:`obsolete`: The package has been obsoleted by a different update

:ref:`revoked`: The update was removed before it reached the testing repository.

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


.. _testing:

Testing
=======

The testing status means that the update has been pushed to its release's testing repository. While
in the testing repository users may provide feedback via karma and comments. Once enough feedback is
generated, Bodhi's web interface can be used to release the update by clicking
'Mark as Stable', or it can be removed by using 'Delete'. The command line interface can
also be used to perform these actions.

If the update is configured to use the 'autopush', it will automatically be pushed or unpushed based
on the feedback from testers. This feature can be disabled if you wish to push your update to the
stable repository manually. By default, if your update achieves a karma of 3, it will automatically
be pushed to stable, and will be unpushed if it reaches -3.

Testing also has two possible substates, both expressed as the "request", that occur when your
package is ready to go to stable. These are documented in the next two sections.


.. _testing-stable:

Testing/Stable
==============

The "stable" state means that the package will be sent out to the stable
repositories the next time a Release Engineer runs the update push command. The update will remain
in the testing repository during this state.


.. _stable:

Stable
======

After an update is pushed to the stable repository, it is marked as stable in Bodhi. At this point,
Bodhi will close associated bugs, and will send out update notices to the appropriate e-mail
addresses.


.. _sidetag-active:

Side_tag_active
===============

An update can be created as a side tag. This corresponds to the request for a Koji side tag, which is
a build target used to collect and iterate builds temporarily. This allows builds to be iterated without
interfering with content in tags that ship to consumers. Once the builds are complete and correct, the
side tag can then be merged into an existing tag.


.. _sidetag-active-testing:

Side_tag_active/Testing
=======================

The side tag enters this state when it is requested to merge. This happens for example when the
release requires human feedback and the appropriate waiting period or karma threshold has been
reached. When the merge completes, the side tag update's state passes to pending testing as with
any other update.


.. _sidetag-active-stable:

Side_tag_active/Stable
======================

The side tag enters this state when requested to push to stable, for example, when it requests tests
to be run on builds without human feedback. If the tests pass, Bodhi tries to merge the side tag. If
that is successful, the update passes to the stable state.


.. _sidetag-expired:

Side_tag_expired
================

A side tag update has a specific lifetime that is set in Bodhi configuration.  After this update's
lifetime has passed, its state is moved to expired, the underlying update object and all content is
deleted, and the koji side tag is also deleted.


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

The developer has decided to pull the update from the testing repository. This state can only be
reached if the update is in the testing state.
