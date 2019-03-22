===============
Testing updates
===============

Bodhi's primary use case is to gate proposed software updates based on testing feedback. Feedback
can be provided automatically by CI systems, or can be provided by humans through comments and
karma.


Karma
=====

Authenticated users may post positive or negative karma onto an update, along with a comment to
describe their experience. Once the update reaches its karma threshold (set by the packager), it may
be pushed out to the stable repositories. This will happen automatically if the update is configured
to use Bodhi's autokarma system, or manually by the packager if it is not.

Some updates will offer testers additional types of karma. Critical path updates will offer the user
a "critical path karma" option, which asks the tester if the system's basic functionality is
preserved with the update (for example, does the system still boot). Some updates are associated
with Bugzilla tickets, and these updates will allow the tester to mark whether they think the given
bug is addressed by the update. Updates may also be linked to Wiki documents that describe a testing
plan for the associated packages, and the tester may provide feedback for each of the wiki test
pages as well.


Automated tests
===============

Bodhi may also provide feedback from automated test systems if it is configured to do so. To view
this feedback, click on the update's "Automated Tests" tab.

Bodhi may also be configured to query `Greenwave`_ for automated test based gating decisions on
updates. If this is enabled, the update's web page will display the current status of Greenwave's
gating decision.


.. _Greenwave: https://pagure.io/greenwave
