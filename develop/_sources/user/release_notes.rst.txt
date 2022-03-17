=============
Release notes
=============

.. towncrier release notes start

v5.7.5
======
This is a feature release.

Features
^^^^^^^^

* Prepare the Bodhi client to be compatible with an OIDC-enabled server.
  (:pr:`4391`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Aurélien Bompard


v5.7.4
======
This is a bugfix release that should help with several more problems after 7.5.3 release.


Features
^^^^^^^^

* Automatic updates consumer can now identify new packages and mark updates
  with the appropriate type (:pr:`4324`).
* Detect stuck updates with builds that were never been sent to pending-signing
  and unstuck them (:issue:`4307`).

Bug fixes
^^^^^^^^^

* Bodhi will now retry to get a build changelog if Koji returns empty rpm
  headers. See also https://pagure.io/koji/issue/3178 (:issue:`4316`).
* Fixed an issue about some bug title never fetched from Bugzilla
  (:issue:`4317`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Adam Saleh
* Aurélien Bompard
* Adam Williamson
* Lenka Segura
* Mattia Verga


v5.7.3
======
This is a bugfix release that should help with several more problems after 7.5.2 release.


Bug fixes
^^^^^^^^^

* Fixed an issue where Bodhi was throwing 5xx "NoSuchColumnError testcases.id" errors because of a misconfigured table (:issue:`4302`).

v5.7.2
======
This is a bugfix release that should help with several problems after 7.5.1 release.


Bug fixes
^^^^^^^^^

* Fixed an issue where JSON serialization of a TestCase object hangs the server
  (:pr:`4278`).
* Fixed a possible call to Koji listTagged() passing an empty tag name
  (:pr:`4280`).
* Bodhi will now try to resubmit a build to signing if it detects that is stuck
  in pending signing for some time (:pr:`4300`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Adam Saleh
* Mattia Verga


v5.7.1
======
This is a bugfix release.

Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

This release contains database migrations. To apply them, run::

    $ sudo -u apache /usr/bin/alembic -c /etc/bodhi/alembic.ini upgrade head


Summary of the migrations:

* Add End of life (eol) field to the releases (:pr:`4241`).

Backwards incompatible changes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Query on both relevant Greenwave decision contexts for critical-path updates.
  `Update.get_test_gating_info()` now returns a list of decision dictionaries,
  not a single decision dictionary. The API endpoint
  `/updates/{id}/get-test-results` similarly now returns a single-key
  dictionary whose value is a list of decisions, not a single decision
  dictionary. (:issue:`4259`).

Features
^^^^^^^^

* Added support for release names ending with "N" such as EPEL next
  (:pr:`4222`).
* Set a `delta` parameter of 30 days when quering datagrepper for bodhi-related
  user activity (:pr:`4255`).
* Added support for setting flags in generated advisories to require logging
  out and logging back in for the update to take effect (:issue:`4213`).
* Replace Greenwave decision change message consumer with ResultsDB and
  WaiverDB message consumers (:issue:`4230`).

Bug fixes
^^^^^^^^^

* Fix an issue that caused the builds in a side-tag update to not be tagged
  correctly when the build list of the update was modified (:pr:`4161`).
* Bodhi will now delete the side-tag in Koji when an update is pushed to
  stable. Builds that were tagged in the side-tag but were not pushed as part
  of the update will be untagged. This is required to make sure to not leave
  stale side-tags in the Koji database (:pr:`4228`).
* Updates for archived releases cannot be edited anymore (:pr:`4236`).
* Correctly mark automatic updates as critpath when appropriate
  (:issue:`4177`).
* Fixed an issue with validators that prevents inconsistent refusal of bodhi
  override with maximum duration (:issue:`4182`).
* Fixed an issue where the search result box was cutted off out of screen
  borders (:issue:`4206`).
* Fixed a javascript bug which prevented the "waive tests" button to be
  displayed in UI (:issue:`4208`).
* Fixed an issue with validators that prevented a side-tag update owner to edit
  their update after adding a build for which they don't have commit access
  (:issue:`4209`).
* Avoid gating status ping-pong on update creation, assume status 'waiting' for
  2 hours or until first failed test (:issue:`4221`).
* For new packages submitted to repositories, the changelog was not generated
  and attached to the automatic Update. This prevented the bugs mentioned in
  the changelog to be closed by Bodhi (:issue:`4232`).
* Staging Bodhi now uses staging Bugzilla URL for bug links (:issue:`4238`).
* Fixed an issue where editing Updates always caused to set the request to
  Testing (:issue:`4263`).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* Add End of life (eol) field to the releases (:issue:`4240`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Adam Saleh
* Adam Williamson
* Clement Verna
* dalley
* Justin Caratzas
* Jonathan Wakely
* Karma Dolkar
* Kevin Fenzi
* Lenka Segura
* Mattia Verga
* Miro Hrončok
* Michael Scherer
* Andrea Misuraca
* Neal Gompa
* Patrick Uiterwijk
* Pierre-Yves Chibon
* Rayan Das
* Samyak Jain
* Sebastian Wojciechowski
* Tomas Hrcka

v5.7.0
======
This is a feature release.


Features
^^^^^^^^

* Query different Greenwave contexts for critical path updates, allowing for
  stricter policies to apply (:pr:`4180`).
* Use Pagure's `hascommit` new endpoint API to check user's rights to
  create/edit updates. This allow collaborators to push updates for releases
  for which they have commit access. (:pr:`4181`).

Bug fixes
^^^^^^^^^

* Fixed an error about handling bugs in automatic updates (:pr:`4170`).
* Side-tag wheren't emptied when updates for current releases were pushed to
  stable (:pr:`4173`).
* Bodhi will avoid sending both 'update can now be pushed' and 'update has been
  pushed' notifications at the same time on updates pushed automatically
  (:issue:`3846`).
* Clear request status when release goes EOL (:issue:`4039`).
* Allow bodhi to not operate automatically on bugs linked to in changelog for
  specific releases (:issue:`4094`).
* Use the release git branch name to query PDC for critpath components
  (:issue:`4177`).
* Avoid using datetime.utcnow() for updateinfo <updated_date> and <issued_date>
  elements, use "date_submitted" instead. (:issue:`4189`).
* Updates which already had a comment that they can be pushed to stable were
  not automatically pushed to stable when the `stable_days` threshold was
  reached (:issue:`4042`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Adam Saleh
* Adam Williamson
* Clement Verna
* Daniel Alley
* Mattia Verga
* Andrea Misuraca


v5.6.1
======
This is a bugfix release.


Bug fixes
^^^^^^^^^
Fix two reflected XSS vulnerabilities - CVE: CVE-2020-15855


Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Patrick Uiterwijk

v5.6
====
This is a feature release.


Dependency changes
^^^^^^^^^^^^^^^^^^

* Drop support for bleach 1.0 api (:pr:`3875`).
* Markdown >= 3.0 is now required (:pr:`4134`).

Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

This release contains database migrations. To apply them, run::

    $ sudo -u apache /usr/bin/alembic -c /etc/bodhi/alembic.ini upgrade head


Features
^^^^^^^^

* Added a `from_side_tag` bool search parameter for Updates and allow searching
  for that and for gating status from WebUI (:pr:`4119`).
* Allow overriding `critpath.stable_after_days_without_negative_karma` based on
  release status (:pr:`4135`).
* Users which owns a side-tag can now create updates from that side-tag even if
  it contains builds for which they haven't commit access (:issue:`4014`).

Bug fixes
^^^^^^^^^

* Fix encoding of package and user names in search results (:pr:`4104`).
* Fix autotime display on update page (:pr:`4110`).
* Set update.stable_days to 0 for Releases not composed by Bodhi itself
  (:pr:`4111`).
* Ignore builds in Unpushed updates when checking for duplicate builds
  (:issue:`1809`).
* Make automatic updates obsolete older updates stuck in testing due to failing
  gating tests (:issue:`3916`).
* Fix 404 pages for bot users with nonstandard characters in usernames
  (:issue:`3993`).
* Fixed documentation build with Sphinx3 (:issue:`4020`).
* Serve the documentation directly from the WSGI application using WhiteNoise.
  (:issue:`4066`).
* Updates from side-tag for non-rawhide releases were not pushed to testing
  (:issue:`4087`).
* Side-tag updates builds were not editable in the WebUI (:issue:`4122`).
* Fixed "re-trigger tests" button not showed on update page (:issue:`4144`).
* Fixed a crash in automatic_updates handler due to `get_changelog()` returning
  an unhandled exception (:issue:`4146`).
* Fixed a crash in automatic_updates handler due to trying access update.alias
  after the session was closed (:issue:`4147`).
* Some comments orphaned from their update where causing internal server
  errors. We now enforce a not null check so that a comment cannot be created
  without associating it to an update. The orphaned comments are removed from
  the database by the migration script. (:issue:`4155`).
* Dockerfile for pip CI tests has been fixed (:issue:`4158`).

Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* Rename `Release.get_testing_side_tag()` to `get_pending_testing_side_tag()`
  to avoid confusion (:pr:`4109`).
* Added F33 to tests pipeline (:pr:`4132`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Adam Saleh
* Clement Verna
* Justin Caratzas
* Jonathan Wakely
* Karma Dolkar
* Mattia Verga
* Pierre-Yves Chibon
* Rayan Das
* Sebastian Wojciechowski


v5.5
====
This is a bugfix release.


Bug fixes
^^^^^^^^^

* Disable manual creation of updates for releases not composed by Bodhi and add
  some bits in the docs on how to handle automatic updates not being created
  (:issue:`4058`).
* Fix TestCase validation upon feedback submission (:issue:`4088`).
* Do not let update through when bodhi fails to talk to greenwave.
  (:issue:`4089`).
* Fix package name encoding in URLs (:issue:`4095`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Adam Saleh
* Clement Verna
* Karma Dolkar
* Mattia Verga
* Pierre-Yves Chibon


v5.4.1
======
This is a {major|feature|bugfix} release that adds [short summary].


Bug fixes
^^^^^^^^^

* Make sure to close the bugs associated to a rawhide update. (:issue:`4067`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Clement Verna
* Mattia Verga


v5.4.0
======
This is a minor release.


Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

This release contains database migrations. To apply them, run::

    $ sudo -u apache /usr/bin/alembic -c /etc/bodhi/alembic.ini upgrade head


Summary of the migrations:

* Migrate relationship between TestCase and Package to TestCase and Build. The migration script will take care of migrate existing data to the new relation.
* The user_id column in comments table has been set to be not nullable.
* The notes column in buildroot_overrides table has been converted to UnicodeText (from Unicode).

Bug fixes
^^^^^^^^^

* Associate TestCase to Build instead of Package, allowing to remove old
  testcases from updates (:issue:`1794`).
* Replace koji krb_login with gssapi_login. (:issue:`4029`).
* Making sure that builds of side tag update for normal releases are marked as
  signed. (:issue:`4032`).
* Handle Cornice 5.0 JSON error handling. (:issue:`4033`).
* Cap buildroot overrides notes to a maximum of 2k characters and convert the
  database field to UnicodeText (:issue:`4044`).

Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* The user_id field in the comments table has been made not nullable. Some
  database joins have been tweaked to get better performance (:pr:`4046`).
* Always use koji.multiCall for untag/unpush for better handle updates with a
  lot of builds (:pr:`4052`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Clement Verna
* Karma Dolkar
* Mattia Verga
* Miro Hrončok
* Sebastian Wojciechowski


v5.3.0
======
This is a minor release.


Dependency changes
^^^^^^^^^^^^^^^^^^

* Splitted handle_update task into two celery tasks for bugs and testcases.
  These two new tasks will make use of Celery's `autoretry_for` and
  `retry_backoff` features to circumvent external services connection problems.
  `retry_backoff` needs Celery >= 4.2 (:pr:`3989`).

Features
^^^^^^^^

* Associate bugs mentioned in rpm changelog to automatically created Rawhide
  updates; the bugs mentioned with the format `fix(es)|close(s)
  (fedora|epel|rh|rhbz)#BUG_ID` will be associated to the update and
  automatically closed (:issue:`3925`).

Bug fixes
^^^^^^^^^

* Use jquery-typeahead for bodhi searchbar and always show the input field
  (:issue:`1455`).
* Reset update.date_testing when editing builds (:issue:`3493`).
* Removed pending_testing tag when self.request is still in
  UpdateRequest.testing (:issue:`3944`).
* Fix the broken privacy policy link for update's comment box. (:issue:`3971`).
* Do not bound the database session created using TransactionalSessionMaker
  class to the object created.
  Since threads are sharing the memory binding to the session object, it makes
  it possible for threads to
  override a previous session leading to unexpected behaviours.
  (:issue:`3979`).
* Editing builds in an update should not remove override tags (:issue:`3988`).
* Make Test Cases look clickable. (:issue:`4003`).
* If an update include no builds, use alias as title (:issue:`4012`).

Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* Revise display for update's settings

  Showed a 'stable by karma: disabled' and a 'stable by time: disabled' in
  the UI when appropriate. Also added a 'Autotime: <Bool>' to the CLI output.
  (:issue:`3957`).
* Avoid using a database session in the tag_update_builds_task.
  (:issue:`3981`).
* Avoid using a database session in the handle side tag task. (:issue:`3983`).
* Ignore celery task's results we don't use. (:issue:`3995`).

Documentation improvements
^^^^^^^^^^^^^^^^^^^^^^^^^^

* Reference the state that happens when an update is revoked (:issue:`2902`).
* Document the full set of bug trackers that can be reference in Bodhi's
  markdown.
  Also added a section to Bodhi's Sphinx docs about Bodhi markdown,
  and listed the bug trackers there as well. (:issue:`3209`).
* Add information to Bodhi docs that Bodhi has frozen release state
  (:issue:`3505`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Clement Verna
* Karma Dolkar
* Mattia Verga
* Richard O. Gregory
* Tomas Kopecek


v5.2.2
======
This is a bugfix release.


Bug fixes
^^^^^^^^^

* Only pass scalar argument to celery (part 2). Avoid the celery enqueuer
  emitting SQL queries to resolve attributes, and therefore opening new
  transactions. (:issue:`8b30a825`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Clement Verna


v5.2.1
======
This is a bugfix release.


Bug fixes
^^^^^^^^^

* Get the update object in the celery worker from the database.
  (:issue:`3966`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Clement Verna


v5.2.0
======
This is a feature and bugfix release.


Features
^^^^^^^^

* Added `__current__`, `__pending__` and `__archived__` macro filters to
  quickly filter Updates by Release status (:pr:`3892`).
* Added search filtering capabilities to the Overrides page (:pr:`3903`).
* Output the update install command into the bugs comments. Also change the
  `stable_bug_msg` and `testing_bug_msg` settings format to use placeholders in
  place of `%s`: if you have customized these settings you will need to adjust
  them to the new format. Here it is the list of the available placeholders:
  `{update_title}, {update_beauty_title}, {update_alias}, {repo},
  {install_instructions}, {update_url}` (:issue:`740`).
* Tag builds for updates asynchronously using Celery tasks. (:issue:`3061`).
* Add a Liveness and Readyness endpoints for OpenShift probes. (:issue:`3854`).
* Allow revoking the `push to stable` action (:issue:`3921`).

Bug fixes
^^^^^^^^^

* Place 404 Not Found in the middle of the website (:pr:`3835`).
* RPM changelog was not automatically added in the notes for Rawhide updates as
  expected (:pr:`3931`).
* Add back the ability to add abitairy text as a build. (:issue:`3707`,
  :issue:`3765`).
* Allow to comment on update that were pushed to stable. (:issue:`3748`).
* Make comments submission to use common code with other forms and avoid
  clearing the spinner until the page refreshes (:issue:`3837`).
* Try to avoid timeout error when requesting latest_candidates with
  `hide_existing=true` (:issue:`3841`).
* Allow task id to be null in the bodhi.update.status.testing message schema.
  (:issue:`3852`).
* Sent UpdateReadyForTestingV1 only for rpm (:issue:`3855`).
* Prevent whitespaces string to be set as display name of an update
  (:issue:`3877`).
* Fixed pagination issue when using multiple values for the same filter
  (:issue:`3885`).
* Make sure we send the fedora-messaging messages before trigerring a celery
  task. (:issue:`3904`).
* Prevent updates from sidetags being stuck in Testing (:issue:`3912`).
* Do not allow to push back to testing a stable update (:issue:`3936`).

Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* Use existing db session when creating a package: `Package.get_or_create()`
  now requires a session object in input (:pr:`3860`).
* Use koji's multicall in `tag_update_builds` task (:pr:`3958`).

Other changes
^^^^^^^^^^^^^

* Use Celery Beat instead of cron jobs. The corresponding CLIs have been
  adjusted
  to trigger the task. They will still block until the task is done, but it may
  not be running on the host that the CLI was called on. The affected CLIs are:
  ``bodhi-clean-old-composes``, ``bodhi-expire-overrides``,
  ``bodhi-approve-testing``, and ``bodhi-check-policies`` (:issue:`2867`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Adam Saleh
* Aurélien Bompard
* Adam Williamson
* Clement Verna
* Eli Young
* Karma Dolkar
* Mattia Verga
* Michal Konečný
* Nils Philippsen
* Pierre-Yves Chibon
* Elliott Sales de Andrade
* Richard O. Gregory
* Rick Elrod
* Ryan Lerch
* Stephen Coady
* subhamkrai
* Sebastian Wojciechowski


v5.1.1
======

This is a bugfix release.

Bug fixes
^^^^^^^^^

* Fix the Fedora Messaging exception caught for publish backoff (:pr:`3871`).
* Only pass scalar arguments to celery tasks to avoid lingering database
  transactions (:pr:`3902`).
* Fix bug title escaping to prevent a JS crash while editing updates
  (:issue:`3714`).
* Fix potential race condition with the celery worker accessing an update
  before the web request was commited. (:issue:`3858`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Aurélien Bompard
* Clement Verna
* Mattia Verga


v5.1.0
======

This is a feature and bugfix release.

Features
^^^^^^^^

* Include the task id for each build when notifying that an update is ready to
  be tested (:issue:`3724`).
* Linkify update aliases in comments (:issue:`776`).

Bug fixes
^^^^^^^^^

* Fix BuildrootOverrides editing/expiring from the UI (:issue:`3710`).
* Fix the traceback when builds are being signed without being included in an
  update (:issue:`3720`).
* Increase the size of the update alias column (:issue:`3779`).
* Fix JS error when removing a bug from the list in the update form
  (:pr:`3796`).
* Disable warnings when adding `Security Response` bugs to an update
  (:issue:`3789`).
* Manage single build update conflicting builds. (:issue:`3828`).

Contributors
^^^^^^^^^^^^

The following developers contributed to this release of Bodhi:

* Aurélien Bompard
* Clement Verna
* Mattia Verga
* Pierre-Yves Chibon
* Rick Elrod
* Ryan Lerch


v5.0.0
======

This is a major release with many backwards incompatible changes.


Backwards incompatible changes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Celery is introduced to handle the long-running tasks (:issue:`2851`).
* Fedmenu was removed from the UI (:issue:`2194`).
* Remove deprecated ``search_packages`` path (:pr:`3411`).
* Remove ``critpath_karma`` from the UI (:issue:`2194`).
* Remove unused and incorrect ``server.bugs.Bugzilla.get_url()`` function.
* Print errors to stderr in command line tools.


Dependency changes
^^^^^^^^^^^^^^^^^^

* Celery is a new required dependency (:issue:`2851`).


Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

This release contains database migrations. To apply them, run::

    $ sudo -u apache /usr/bin/alembic -c /etc/bodhi/alembic.ini upgrade head


Features
^^^^^^^^

* Update fedora-bootstrap to latest 1.5.0.
* Add ctype to the ComposeComplete (:issue:`3297`).
* Add knowledge of branch freezes to the Release model (:issue:`1038`, :issue:`1563`).
* API: Create/edit updates from Koji tags (:issue:`3009`).
* Add javascript confirmation for unpushing updates.
* Use versioned dir name for static files.
* Improve the performance of validate_build_uniqueness.
* Add option to create/edit updates side tags to CLI (:issue:`2325`).
* Overhaul the new update form.
* Mark updates not composed by bodhi as pushed when stable.
* Allow multiple status params for update list views (:issue:`3429`).
* Send a message when an update is ready to be tested (:issue:`3428`).
* Create additional side tags on multi build tag (:issue:`3473`).
* Create comment when CI tests starts, but don't send an email (:issue:`3403`).
* Add support for creating sidetag updates to webui.
* Create a Dashboard for logged in users.
* Clean up Javascript, CSS and fonts.
* Add a new config item, ``automatic_updates_blacklist``, which is a list of
  users to not process auto updates from.
* Document what the update states mean for rawhide.
* Add a filtering/searching interface to the updates query view.
* Add the list of packages in the update description to rss feed.
* Transform markdown code to html for better readability of the rss feed.
* Add frozen release state to bodhi releases list.
* Add API call to retrigger update tests.
* Tidy up the UI.
* Add --user and --password to all actions of the bodhi CLI supporting
  --openid-api (for example: waive and trigger) (:pr:`3550`).
* Update ChartJS package and redesign Release page (:pr:`3671`).
* Automatically created updates (e.g. Fedora Rawhide single package updates)
  now include a changelog entry in the update notes. (:issue:`3192`).
* Move multi build update that failed to merge in rawhide to pending.
  (:issue:`3514`).


Bug fixes
^^^^^^^^^

* Handle connection problems when talking to Wiki (:issue:`3361`).
* Make Bodhi able to clear models.Release._all_releases cache (:issue:`2177`).
* Query Greenwave in batches to avoid timeouts.
* Template, js and style fixes.
* Allow to configure a release without an override tag (:issue:`3447`).
* Determine a release for sidetag updates (:issue:`3480`).
* Change update status to testing if every build is signed (:issue:`3475`).
* Delete additional tags once an side tag update was pushed to stable (:issue:`3476`).
* Turn off autokarma and autotime for automatic updates (:issue:`3424`).
* Make ``display_name`` optional in template (:issue:`3470`).
* Sign new builds to ``<sidetag>-pending-signing`` (:issue:`3485`).
* Allow only 1 update per side tag (:issue:`3484`).
* Disable comments on updates when update is pushed and stable (:issue:`2050`).
* Unify rawhide simple build update with multi build update (:issue:`3513`).
* Prevent crash when compose contains update without builds (:issue:`3471`).
* Added build.update.pushed = True for the signed consumer so that it can be
  unpushed. (:issue:`3625`).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* Rename bteststyle to blint.
* Update developer documentation.
* Run mypy directly in Vagrant (:issue:`3335`).
* More type annotations.
* Add WaiverDB and Greenwave to development environment (:issue:`3011`).
* Provide authentication in the integration testing environment.
* Make it easier to develop using VS Code.
* Add option to vagrant provisioning to use stg infra.
* Introduction of `Towncrier <https://github.com/hawkowl/towncrier/>`_ to
  manage the release notes (:issue:`3562`).


Other changes
^^^^^^^^^^^^^

* List items in RSS feed starting from the most recent (:pr:`3621`).


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 5.0.0:

* Anatoli Babenia
* Aurélien Bompard
* Randy Barlow
* Clement Verna
* David Fan
* dimitraz
* Lukas Holecek
* Mattia Verga
* Michal Konečný
* Nils Philippsen
* Ondrej Nosek
* Pierre-Yves Chibon
* Rick Elrod
* Ryan Lerch
* Robert Scheck
* Rob Shelly
* Sam Robbins
* Stephen Coady
* siddharthvipul
* subhamkrai
* Sebastian Wojciechowski


v4.1.0
======

This is a feature release that adds single-package gating.

Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

This release contains database migrations. To apply them, run::

    $ sudo -u apache /usr/bin/alembic -c /etc/bodhi/alembic.ini upgrade head


Features
^^^^^^^^

* Add autopush and stable_days to an update.  When ``autopush`` is true, the
  approve_testing cronjob will push the update to stable if it has meet the
  testing requirements (``stable_days``).  ``stable_days`` cannot be smaller
  than the release ``mandatory_days_in_testing`` (:issue:`2978`).
* Add a login reminder for posting feedback.
* Add ``package_manager`` enum and ``testing_repository`` string to Release
  model.  No default is provided, so if one wants Bodhi to display the install
  command for an update, they need to manually edit the existing releases after
  the database migration.
* Add a Greenwave message consumer to update the ``test_gating_status`` value.
* Add the flatpak releases to the greenwave config.
* Automatically create Rawhide updates in ``testing`` state.


Bug fixes
^^^^^^^^^

* Log permanent failures for debugging.  Previously, exceptions were raised
  which caused the affected messages to be placed back into the queue
  (:issue:`3306`).
* Fix downloading packages for updates with multiple builds.
* Verify the correct number of received items in the client.
* Do not ask for original_spec_nvr results from greenwave.  This will have for
  effect to improve the performance of bodhi's requests to greenwave.
* Bodhi will now retry for up to 10 minutes if it receives ``koji.AuthError``
  (:issue:`1201`).
* Don't raise Exception on non-existing composes (:issue:`3318`).
* Correct grammar on a comment that Bodhi writes.
* Log unsuccessful attempt to set request as INFO (:issue:`3293`).
* Use update.alias instead of update.title in updates rss link.
* Make sure ``%{uid}`` in krb ccache gets replaced with the effective UID.
* Create composes based on update's alias in bodhi-push (:issue:`3160`).
* User should be able to set ``Update.display_name`` (:issue:`1369`).
* Make ``meets_testing_requirements()`` comply with policy
  (:issue:`1307`, :issue:`1508`, :issue:`1796`, :issue:`3282`).
* Order builds by nvr in all places so the ordering is always consistent.


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* Leave the global log level in peace when testing.
* Update the Developer documentation
* Disable ``warm_cache_on_start`` in unittest (:issue:`3311`).
* Use flake8-import-order to enforce PEP-8 imports.


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 4.1.0:

* Aurélien Bompard
* Clement Verna
* Mattia Verga
* Michal Konečný
* Nils Philippsen
* Patrick Uiterwijk
* Pierre-Yves Chibon
* Randy Barlow
* Sebastian Wojciechowski
* Troy Dawson


v4.0.2
======

This is a bugfix release.


Bug fixes
^^^^^^^^^

* Drop updateinfo <id> tag detection (:issue:`3269`).


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 4.0.2:

* Patrick Uiterwijk


v4.0.1
======

This is a bugfix release.


Bug fixes
^^^^^^^^^

* Fix zchunk updateinfo getting injected as updateinfo_zck (:issue:`3261`).
* Fix a broken template in ``bodhi-push`` (:issue:`3256`).


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 4.0.1:

* Randy Barlow
* Patrick Uiterwijk


v4.0.0
======

This is a major release with many backwards incompatible changes.


Backwards incompatible changes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Values NULL and 0 are not allowed in update's stable_karma and unstable_karma (:issue:`1029`).
* Updates no longer have a ``title`` attribute. This affects many elements of Bodhi's REST API,
  including URLs (update titles can no longer be used to reference updates, only aliases), REST API
  data structures, and Bodhi's messages (:issue:`186`, :issue:`1542`, :issue:`1714`, and
  :issue:`1946`).
* The ``prefer_ssl`` setting has been renamed to ``libravatar_prefer_tls`` and now defaults to
  ``True`` instead of ``None`` (:issue:`1921`).
* Integration with pkgdb is no longer supported (:issue:`1970`).
* The ``/admin/`` API has been removed (:issue:`1985`).
* The relationship between Packages and Users was dropped. As a result, the ``packages``
  parameter in users query API has also been removed (:issue:`1997`).
* Support for CVE tracking was dropped. It was technically not possible to use the feature, so it
  is unlikely to affect any deployments (:issue:`1998`).
* The ``processing`` update status has been removed (:issue:`1999`).
* The ``/masher`` API has been removed (:issue:`2024`).
* Default sqlalchemy.url setting points to PostgreSQL instead of SQLite (:issue:`2040`).
* The ``Masher`` was renamed to ``Composer``. As a result, the ``bodhi-clean-old-mashes`` script
  was renamed to ``bodhi-clean-old-composes``, notification topics ``mashtask.start``,
  ``mashtask.mashing``, ``mashtask.complete``, ``mashtask.sync.wait`` and ``mashtask.sync.done``
  was renamed to ``compose.start``, ``compose.composing``, ``compose.complete``, ``compose.sync.wait``
  and ``compose.sync.done``, configuration settings ``mash_dir``, ``mash_stage_dir`` and
  ``max_concurrent_mashes`` was renamed to ``compose_dir``, ``compose_stage_dir`` and
  ``max_concurrent_composes`` (:issue:`2151`).
* The ``bodhi-monitor-composes`` script has been removed (:issue:`2171`).
* The stacks feature has been removed (:issue:`2241`).
* The ``bodhi-manage-releases`` script has been removed (:issue:`2420`).
* Support for anonymous comments was dropped. As a result, the ``anonymous`` field on the Comment
  object was removed and comments query API parameter ``anonymous`` was dropped. All ``captcha.*``
  settings were removed (:issue:`2700`).
* Bodhi client and server no longer support Python 2. Python 3.6+ are the only supported Python
  releases (:issue:`2759`).
* Support for the ``ci_url`` on the ``Build`` object was dropped (:issue:`2782`).
* Support for ``active_releases`` parameter in updates query API was dropped (:issue:`2815`).
* Support for fedmsg has been dropped (:issue:`2838`).
* The ``/updates/ALIAS/TITLE`` API has been removed (:issue:`2869`).
* Support for update's old_updateid was dropped (:issue:`2903`).
* The UI no longer has fedmsg integrations to show events happening elsewhere in Bodhi
  (:issue:`2913`).
* Support for update's greenwave_unsatisfied_requirements was dropped (:issue:`2958`).
* The batching feature was dropped, and thus updates can no longer be in the batched request state.
  As a result, the bodhi-dequeue-stable CLI has also been removed (:issue:`2977`).
* Support for obsolete scripts in ``tools`` folder was dropped (:issue:`2980`).
* Support for update's greenwave_summary_string has been dropped (:issue:`1339` and :issue:`2988`).
* Bug objects no longer include a ``private`` field (:issue:`3016`).
* The CLI now defaults to the ``--wait`` flag when creating or editing buildroot overrides. The old
  behavior can be achieved with the ``--no-wait`` flag (:issue:`3006`).
* All messages and API responses that serialize updates no longer have a ``submitter`` field. This
  was redundant with the included ``user.name`` field, and was only in place for compatibility with
  Bodhi 1 which was EOL many years ago (:issue:`3144`).
* All of Bodhi's fedmsgs have been changed. A new bodhi.messages packages has been added with new
  published message schemas. Note that only the fields listed in the documented schemas are
  supported in Bodhi 4, even though Bodhi still sends messages similar to the messages it sent in
  the past. Message consumers should not rely on any undocumented fields in these messages. If you
  need information that is not included in the supported schema, please work with the Bodhi project
  to get the schema adjusted accordingly. Bodhi's messages are now documented in
  :doc:`../server_api/index`.
* The ``fedmsg_enabled`` setting was removed, since fedmsg is not used anymore.


Dependency changes
^^^^^^^^^^^^^^^^^^

* pkgdb is no longer required (:issue:`1970`).
* cryptography is no longer required (:issue:`2700`).
* Fonts are no longer required for the captcha (Bodhi previously defaulted to using
  liberation-mono-fonts, but this wasn't a strict requirement since the font was configurable)
  (:issue:`2700`).
* pillow is no longer required (:issue:`2700`).
* six is no longer required for the client or server (:issue:`2759`).
* ``bodhi-server`` now depends on ``bodhi-messages``.
* kitchen is no longer required (:issue:`3094`).
* hawkey is no longer required.
* PyYAML is now a required dependency (:issue:`3174`).
* Bodhi now requires Python 3.6 or greater (:issue:`2856`).
* Bodhi no longer uses or works with ``fedmsg``.
* Backoff is now a required dependency (:issue:`3237`).


Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The Bodhi server must be upgraded from Bodhi 3.13.0 or newer to 4.0.0 (i.e., it is not supported to
upgrade a server older than 3.13.0 directly to 4.0.0 as 4.0.0 has trimmed database migrations from
the older releases.

This release contains database migrations. To apply them, run::

    $ sudo -u apache /usr/bin/alembic -c /etc/bodhi/alembic.ini upgrade head


Features
^^^^^^^^

* Bodhi now provides a ``RateLimiter`` log filter and documents how to use it. Together with
  ``pyramid_sawing`` it is now possible to get rate limited e-mail tracebacks from the web server
  (:issue:`969`).
* All updates in a release are set to obsolete status when the release is archived (:issue:`2204`).
* Bodhi will now comment on updates when their test gating status changes (:issue:`2210`).
* ``bodhi-push`` now blocks composing retired releases (:issue:`2555`).
* A new ``bodhi.messages`` Python package has been added as a convenience for Python consumers
  who wish to subscribe to Bodhi's messages (:issue:`2842`).
* Bodhi can now create zchunked ``updateinfo.xml`` files (:issue:`2904`).
* The server has a new ``warm_cache_on_start`` setting, defaulting to ``True``. It is mostly
  useful when developing Bodhi and controls whether the Bodhi initialization should build caches or
  not (:issue:`2942`).
* The compose states are now documented (:issue:`2974`).
* Added a database index on ``build.update_id``, which sped up some common queries
  (:issue:`3038`).
* Log messages are emitted when buildroot overrides are expired to explain why they were expired
  (:issue:`3060`).
* A missing database index was discovered on ``comments.update_id``. Adding it improved performance
  of a common query by about 99.7% and as a result many Bodhi operations are much faster now,
  including update retrieval in the API, CLI, and web UI (:issue:`3062` and :issue:`3201`).
* The CLI now allows users to add and remove builds from updates with ``--addbuilds`` and
  ``--removebuilds`` flags (:issue:`3125`).
* Users can now use markdown to easily reference GCC and Sourceware tickets (:issue:`3129`).
* A new log message is emitted when an update is blocked due to test gating (:issue:`3143`).
* The CLI can now download debuginfo with the new ``--debuginfo`` flag (:issue:`3148`).


Bug fixes
^^^^^^^^^

* Since the ``active_releases`` query parameter was dropped, an issue causing strange pagination
  results is no longer present (:issue:`2316`).
* Waiver details are now displayed in the web UI (:issue:`2365`).
* The JavaScript will no longer crash when run in Fedora's staging environment (:issue:`2523`).
* Fixed a crash in Bodhi's error handler (:issue:`2588`).
* Fixed a crash on the HTML rendering of ``/composes/`` when composes were in a particular state
  (:issue:`2826`).
* Correctly handle ``ConnectionResetError`` in the Composer (:issue:`2850`).
* The CLI's composes info subcommand is now documented in its man page (:issue:`2927`).
* The ``mail.templates_basepath`` setting is now documented (:issue:`2931`).
* Fixed pipeline results showing with heading 'undefined' (:issue:`2969`).
* Compare enum values instead of descriptions (:issue:`3012` and :issue:`3119`).
* The ``bodhi-approve-testing`` script is a lot less chatty (:issue:`3021`).
* Bodhi's API can now serialize internal server errors as JSON so that the clients can properly
  display error messages (:issue:`3035`).
* The ``--composed-by-bodhi`` flag is now documented in the ``bodhi`` man page (:issue:`3085`).
* A variety of spelling and grammatical errors were fixed (:issue:`3131`).
* Bodhi's markdown now uses TLS for links to pear in its markdown (:issue:`3173`).
* Stop using an API that ``dnf`` removed (:issue:`3198`).
* Do not crash on invalid RSS requests (:issue:`3227`).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* Removed flash_log, since it didn't make sense (:issue:`1165`).
* Removed some useless assert statements (:issue:`1200`, :issue:`2848`, and :issue:`2888`).
* An unused enum value was removed (:issue:`1999`).
* The integration tests now run against all supported Fedora releases (:issue:`2824`).
* Bodhi's release process is now documented (:issue:`2918`).
* ``met_testing_requirements()`` got a much needed rename and refactor (:issue:`3158`).
* The Vagrant box now uses the same number of CPUs as the host  (:issue:`3197`).
* Numerous docblock corrections and improvements.
* Introduced type annotation to a few modules and added CI enforcement on them with ``mypy``.
* Numerous improvements have been made to Bodhi's CI tests, including expanded test coverage.
* The Vagrant environment now uses unsafe IO for a small speed boost.
* The integration tests run more efficiently now.


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 4.0.0:

* Adam Williamson
* Anatoli Babenia
* Aurélien Bompard
* Clement Verna
* Jeremy Cline
* Jonathan Dieter
* Josh Soref
* Mattia Verga
* Miro Hrončok
* Nils Philippsen
* Owen W. Taylor
* Patrick Uiterwijk
* Sebastian Wojciechowski
* Troy Dawson
* Randy Barlow


Older releases
==============

.. toctree::
   :maxdepth: 2

   3.x_release_notes
   2.x_release_notes
