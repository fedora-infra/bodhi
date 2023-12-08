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

Some updates are associated with Bugzilla tickets, and these updates will allow the tester to mark
whether they think the given bug is addressed by the update. Updates may also be linked to Wiki
documents that describe a testing plan for the associated packages, and the tester may provide
feedback for each of the wiki test pages as well.


Automated tests
===============

Bodhi may also provide feedback from automated test systems if it is configured to do so. To view
this feedback, click on the update's "Automated Tests" tab.

Bodhi may also be configured to query `Greenwave`_ for automated test based gating decisions on
updates. If this is enabled, the update's web page will display the current status of Greenwave's
gating decision.


Stable push
===========

An update can be pushed to stable repository either manually or automatically, through Bodhi's
`autotime` or `autokarma` features.

For becoming pushable to stable an update must fulfill some criteria set by the associated
release. Typically, each release has `critpath.mandatory_days_in_testing`,
`mandatory_days_in_testing` and `min_karma` values that define thresholds for associated updates
to be pushed to stable. The `mandatory_days_in_testing` settings define an amount of days of
waiting in the updates repository for critical path and non-critical-path updates respectively.
The `min_karma` setting specifies a karma total threshold. An update can be manually pushed to
stable by its submitter or anyone else with edit privileges on the update when **either**
threshold is reached. For example, if a release has a `min_karma` of 2, an update which reaches
+2 karma **can be pushed to stable even if it hasn't reached the `mandatory_days_in_testing`**.

When submitting an update, the user can enable the `autotime` and the `autokarma` features and
set the related values `stable_days` and `stable_karma` for that specific update.
The `stable_days` value defines an amount of days the update must spend in testing repository
before the autopush is done. It must be equal to or greater than the `mandatory_days_in_testing`
value that applies to the update. The `stable_karma` value defines a karma total the update must
reach before the autopush is done. It must be equal to or greater than the release `min_karma`.
Autopush will happen as soon as **either** threshold is reached. For example, if a release has a
`mandatory_days_in_testing` of 7, an update which has `autotime` enabled and `stable_days` set to
10 will be pushable after 7 days **by manual action**, but the autopush will be performed
**after 3 more days**. If an update has both `autotime` and `autokarma` enabled, with thresholds
of 7 days and 3 karma respectively, it will be pushed stable as soon as it reaches +3 karma, even
if 7 days have not yet passed; or it will be pushed stable after 7 days have passed, even if it
has not yet reached +3 karma.

.. _Greenwave: https://pagure.io/greenwave
