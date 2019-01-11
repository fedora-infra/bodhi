=============
Release notes
=============

v3.13.0
-------

This is a feature release.


Deprecations
^^^^^^^^^^^^

* Authentication with OpenID is deprecated (:issue:`1180`).
* ``bodhi-untag-branched`` is deprecated (:issue:`1197`).
* The Update's ``title`` field is deprecated (:issue:`1542`).
* Integration with pkgdb is deprecated (:issue:`1970`).
* Support for Python 2 is deprecated (:issue:`1871` and :issue:`2856`).
* The ``/masher/`` view is deprecated (:issue:`2024`).
* ``bodhi-monitor-composes`` is deprecated (:issue:`2171`).
* The stacks feature is deprecated (:issue:`2241`).
* ``bodhi-manage-releases`` is deprecated (:issue:`2420`).
* Anonymous comments are deprecated (:issue:`2700`).
* The ``ci_url`` attribute on Builds is deprecated (:issue:`2782`).
* The ``active_releases`` query parameter on the Updates query URL is deprecated (:issue:`2815`).
* Support for fedmsg is deprecated (:issue:`2838`).
* Support for Bodhi 1's URL scheme is deprecated (:issue:`2869` and :issue:`2903`).
* The ``/admin/`` API is deprecated (:issue:`2899`).
* The fedmsg UI integration is deprecated (:issue:`2913`).
* CVE support is deprecated (:issue:`2915`).


Dependency changes
^^^^^^^^^^^^^^^^^^

* Bodhi no longer requires ``iniparse`` (:commit:`a910b615`).
* Bodhi now requires ``fedora_messaging`` (:commit:`e30c5f21`).


Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

This release contains database migrations. To apply them, run::

    $ sudo -u apache /usr/bin/alembic -c /etc/bodhi/alembic.ini upgrade head


Features
^^^^^^^^

* A new ``bodhi-shell`` CLI is included with the server package that initialized a Python shell with
  some handy aliases that are useful for debugging Bodhi (:issue:`1792`).
* Updates that obsolete security updates will now be set as security updates themselves
  (:issue:`1798`)
* The CLI no longer crashes when creating multiple buildroot overrides in one command
  (:issue:`2031`).
* The CLI can now display information about waivers (:issue:`2267`).
* Releases can now be marked as not being composed by Bodhi, which will be useful if we want to use
  Bodhi to tag builds into releases without composing those releases, e.g., Fedora Rawhide
  (:issue:`2317`).
* BuildrootOverrides are now prevented for builds that fail the test gating status (:issue:`2537`).
* The web interface now displays instructions for installing updates (:issue:`2799`).
* The CLI now has flags that allow users to override the OpenID API URL to use. This is useful
  for deployments that aren't for Fedora and also for developers, who can use it to authenticate
  against a different OpenID server than Fedora's production instance (Fedora's staging instance is
  nice to use for this) (:issue:`2820`).
* The web UI search box uses a slightly longer delay before issuing the search request
  (:commit:`51c2fa8c`).
* Messages can now be published by ``fedora_messaging``, a replacement for ``fedmsg``
  (:commit:`e30c5f21`).
* Associating updates with private Bugzilla tickets is now handled gracefully (:commit:`7ac316ac`).


Bug fixes
^^^^^^^^^

* The ``bodhi-approve-testing`` CLI script is now more resilient against failures (:issue:`1016`).
* The update edit page will return a HTTP 403 instead of a HTTP 400 if a user tries to edit an
  update they don't have permissions to edit (:issue:`1737`).
* The ``bodhi`` CLI now has a ``--wait`` flag when creating BuildrootOverrides that will cause
  ``bodhi`` to wait on Koji to finish adding the override to the buildroot before exiting
  (:issue:`1807`).
* The waive button is now displayed on locked updates (:issue:`2271`).
* Editing an update with the CLI no longer sets the type back to the default of bugfix
  (:issue:`2528`).
* ``bodhi-approve-testing`` now sets up a log handler (:issue:`2698`).
* Some missing commands were added to the ``bodhi`` man page (:commit:`1e6c2596`).
* A formatting issue was fixed in the command line client (:commit:`996b4ec5`).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* ``bodhi-ci`` now has an integration test suite that launches a live Bodhi server, some of its
  network dependencies, and tests it with some web and CLI requests (:commit:`24304334`).
* ``bodhi-ci``'s status report now displays the run time for finished tasks (:commit:`26af5ef4`).
* ``bodhi-ci`` now prints a continuous status report, which is helpful in knowing what it is
  currently doing (:commit:`f3ca62ad`).
* We now do type checking enforcement on ``bodhi-ci`` (:commit:`2c070055`).


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 3.13.0:

* Aurélien Bompard
* Jeremy Cline
* Mattia Verga
* Ryan Lerch
* Sebastian Wojciechowski
* Vismay Golwala
* Randy Barlow


v3.12.0
-------

This is a small feature release.


Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

No special actions are needed when applying this update.


Features
^^^^^^^^

* Add a new ``bugzilla_api_key`` setting so that Bodhi can authenticate with an API key instead of
  a username and password. It is hoped that this will solve an issue Bodhi has been experiencing
  with Red Hat's Bugzilla instance since it upgraded to version 5, where Bodhi is often told it
  needs to log in to Bugzilla when making changes to issues (:issue:`2827`).
* Logging around Bodhi's use of the Bugzilla API is expanded (:issue:`2831`).


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 3.12.0:

* Randy Barlow


v3.11.3
-------

This is a bugfix release.


Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

No special actions are needed when applying this update.


Bug fixes
^^^^^^^^^

* Correctly handle multiple builds with the search form in the new update JavaScript web UI code
  (:issue:`2791`).


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 3.11.3:

* Mattia Verga


v3.11.2
-------

This is a bugfix release, addressing an issue that was solved incorrectly with 3.11.1.


Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

No special actions are needed when applying this update.


Bug fixes
^^^^^^^^^

* Correctly catch ``http.client.IncompleteRead`` while Composing and retry (:issue:`2758`).


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 3.11.2:

* Randy Barlow


v3.11.1
-------

This is a bugfix release, addressing a few issues with running Bodhi under Python 3.


Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

No special actions are needed when applying this update.


Bug fixes
^^^^^^^^^

* Pass the correct type, str, to ``smtplib.SMTP.sendmail()`` for its to and from address parameters
  (:issue:`2756`).
* Allow ``EnumSymbols`` to be sorted (:issue:`2757`).
* Catch ``http.client.IncompleteRead`` while Composing and retry (:issue:`2758`).
* Correctly handle timestamps from Koji (:issue:`2768`).
* The captcha now works under Python 3 (:issue:`2786`).
* Do not reverse the logout/reboot options in the web UI on Python 3 (:issue:`2778`).


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 3.11.1:

* Patrick Uiterwijk
* Randy Barlow


v3.11.0
-------

Dependency changes
^^^^^^^^^^^^^^^^^^

* Bodhi now fully supports Python 3.
* Bodhi now works with markdown 3 and click 7.
* Bodhi no longer requires pyramid_tm.


Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

This release contains database migrations. To apply them, run::

    $ sudo -u apache /usr/bin/alembic -c /etc/bodhi/alembic.ini upgrade head


Features
^^^^^^^^

* It is now possible to query update by more fields: ``alias``, ``approved-before``,
  ``modified-before``, ``pushed-before``, ``active-releases``, ``severity``, and
  ``submitted-before``, and the fields are documented in the bindings (:issue:`181`).
* It is now possible to query by update title (:issue:`251`).
* It is now possible to filter comments, updates, and overrides with multiple users at once
  (:issue:`2489`).
* The ``bodhi releases`` subcommand now has a ``list`` feature (:issue:`2536`).
* A new compose state was added for waiting on the mirrors to sync updated repositories
  (:issue:`2550`).
* A new server CLI script called ``bodhi-sar`` has been added to retrieve personally identifiable
  information from Bodhi (:issue:`2553`).
* The ``waive`` subcommand is now documented in the ``bodhi`` man page (:issue:`2610`).
* ``bodhi-push`` now has a ``--yes/-y`` flag (:issue:`2635`).
* The ``composes`` and ``releases`` subcommands are now documented in the ``bodhi`` man page
  (:issue:`2642`).
* The composer now logs more information when items are missing from the generated ``repomd.xml``
  file (:issue:`2643`).
* The comment submit button now renders more clearly on some browsers (:issue:`2649`).
* Bodhi is now able to determine container repository names from Koji metadata, instead of
  hard coding it (:issue:`2658`).
* The ``bodhi`` CLI's pagination features are now documented (:issue:`2663`).
* There is now a ``bodhi composes info`` subcommand (:issue:`2683`).


Bug fixes
^^^^^^^^^

* Bodhi now disallows empty comments (:issue:`2009`).
* ``bodhi-check-policies`` now sets up a log handler to silence warnings (:issue:`2156`).
* The ``test_gating_status`` is now set back to waiting when updates are waived (:issue:`2364`).
* Bugzilla permission errors should not cause error e-mails to be sent anymore (:issue:`2431`).
* The waive button is now only displayed if there are failed tests to waive (:issue:`2545`).
* Correctly handle unicode characters in update notes in the CLI (:issue:`2546`).
* The test waiver dialog now shows the test case name (:issue:`2571`).
* Examples were corrected in the ``bodhi`` CLI help text and man page
  (:issue:`2640` and :issue:`2641`).
* The new update web form received a number of improvements and bug fixes. Builds and bugs lists are
  refreshed every time a new package is selected in the input field. Manual added bugs and builds
  are not added to the lists if they are already present after having been retrieved from package
  selection. When an error in AJAX query occurs it is now displayed as an error message. AJAX
  queries now have a timeout. And we now avoid form submit when pressing Enter while entering text
  in the package text input field (:issue:`2648`).
* A misleading composer log entry was corrected (:issue:`2667`).
* An incorrect error message was corrected (:issue:`2703`).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* Bodhi's CI job now reports each test as an individual GitHub status line, which makes it much
  easier to identify the cause of test failures when they occur (:issue:`2584`).
* Due to the above, Mergify is now configured to only enforce passing tests on branched releases,
  since Rawhide failures are often not due to pull request patches (:issue:`2594`).
* Use update.get_url() to generate comments URL (:issue:`2596`).
* Unnecessary repetition was removed from the ``BugTracker`` class (:issue:`2607`).
* A typo was fixed in the docstring of ``Bugzilla.get_url()`` (:issue:`2608`).
* CI now uses the Jenkins Pipeline plugin, which allows us to run the CI jobs much more efficiently,
  and only requires a single node to parallelize the tasks (:issue:`2609`).
* A new development tool, ``devel/ci/bodhi-ci``, was created to replace ``devel/run_tests.sh`` as
  the CI test running tool. It is designed to be useful to developers for running the CI suite
  locally, and has help text to guide you in usage (:issue:`2616`).
* Do not expose the Duffy key in CI logs (:issue:`2617`).
* Use markdown's Extension API to register FFMarkdown instead of an undocumented internal API. This
  allows Bodhi to work with markdown-3.0.0 (:issue:`2618`).
* Explicitly name the skopeo-lite src/dest_creds parameters. Also fix two unit tests for
  click-7.0.0. This allows Bodhi to work with click-7.0.0 (:issue:`2621`).
* Some docstrings were corrected (:issue:`2680`, :issue:`2682`, and :issue:`2689`).
* Upgraded to Mergify 2 (:issue:`2686`).
* Bodhi's tests now run about 40% faster (:issue:`2687`).


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 3.11.0:

* Mattia Verga
* Owen W. Taylor
* Patrick Uiterwijk
* Ryan Lerch
* Sebastian Wojciechowski
* sedrubal
* Randy Barlow


v3.10.1
-------

This releases fixes a crash while composing modular repositories (:issue:`2631`).


v3.10.0
-------

Dependency changes
^^^^^^^^^^^^^^^^^^

The composer now requires hawkey.


Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

This release contains database migrations. To apply them, run::

    $ sudo -u apache /usr/bin/alembic -c /etc/bodhi/alembic.ini upgrade head


Features
^^^^^^^^

* It is no longer an error if a developer tries to create an override for a build that already had
  an override. Instead, Bodhi helpfully edits the old override automatically (:issue:`2030`).
* The UI displays the date that expired overrides became expired (:issue:`2136`).
* Security updates now require severity to be set (:issue:`2206`).
* The Waiver UI now gives the user more context (:issue:`2270` and :issue:`2363`).
* The CLI can be used to edit Release mail templates (:issue:`2475`).
* A new ``clean_old_composes`` setting allows admins to disable the automatic compose cleanup
  feature that was new in Bodhi 3.9.0 (:issue:`2561`).
* The API can filter releases by state (:commit:`beb69a05`).
* The CLI now has a ``--debug`` flag on a couple of commands (:commit:`1bd76179`).
* The bindings have some debug level logging when retrieving Greenwave status (:commit:`b55fa453`).
* The UI now makes it clear that only authenticated users can leave karma on updates
  (:commit:`3b551c32`).
* Bodhi can now manage Flatpaks (:commit:`1a6c4e88`).
* Bodhi now ships a ``/usr/bin/bodhi-skopeo-lite``, which is intended to be an alternative for use
  with the ``skopeo.cmd`` setting. It allows for multi-arch containers and Flatpaks to be managed by
  Bodhi (:commit:`a0496fc9`).
* The composer now uses librepo/hawkey to do much more extensive testing on the produced yum
  repositories to ensure they are valid (:commit:`7dda554a`).


Bug fixes
^^^^^^^^^

* More space was added around some buttons so they don't touch on small screens (:issue:`1902`).
* The ``bodhi releases`` subcommands no longer prompt for password when not necessary
  (:issue:`2496`).
* The submit feedback button now appears on low resolution screens (:issue:`2509`).
* Articles were fixed in a tooltip on the update page (:commit:`075f8a9d`).
* The CLI can again display missing required tests (:commit:`cf75ff81`).
* Fix a failure that sometimes occurred when editing multi-build updates (:commit:`d997ed4f`).
* Unknown Koji tags will no longer cause an Exception when creating new updates
  (:commit:`78dd4aaf`).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* Line test coverage has reached 100% (:commit:`2477fc8f`).
* A fake Pungi is used in the Vagrant environment to speed up ``vagrant up`` (:commit:`1b4f5fcd`).
* No tests are skipped on Python 3 anymore (:commit:`44d46e37`).


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 3.10.0:

* Anatoli Babenia
* Clement Verna
* Mattia Verga
* Owen W. Taylor
* Patrick Uiterwijk
* Pierre-Yves Chibon
* Ralph Bean
* Rick Elrod
* Vismay Golwala
* Randy Barlow


v3.9.0
------

Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

This release contains database migrations. To apply them, run::

    $ sudo -u apache /usr/bin/alembic -c /etc/bodhi/alembic.ini upgrade head


Deprecation
^^^^^^^^^^^

``bodhi-manage-releases`` is now deprecated. The ``bodhi`` CLI now has a ``releases`` section that
performs the tasks that ``bodhi-manage-releases`` is used for.


Dependency changes
^^^^^^^^^^^^^^^^^^

* Cornice must now be at least version 3.1.0 (:issue:`2286`).
* Greenwave is now a required service for Bodhi deployments that wish to continue displaying test
  results in the UI (:issue:`2370`).
* The responses python module is now needed for running tests.


Features
^^^^^^^^

* Bodhi now comments in the same POST as status changes on Bugzilla comments (:issue:`336`).
* The RSS feeds now have titles (:issue:`1119`).
* ``bodhi-clean-old-mashes`` is automatically run after each successful compose (:issue:`1304`).
* The ``bodhi`` CLI can now edit releases' ``pending_signing_tag`` fields (:issue:`1337`).
* White space is stripped when searching for packages or updates (:issue:`2046`).
* Severity is displayed in the web UI (:issue:`2108`).
* Bugzilla bugs are sorted by number on the update bugs tab (:issue:`2222`).
* The web UI now queries Greenwave with each page load to display the test gating status, rather
  than displaying the cached value from Bodhi's database. This allows users to see the current
  status of their update from Greenwave's perspective. This change also causes Bodhi to retrieve the
  test results from Greenwave rather than from ResultsDB, which means the test results tab now shows
  the same test results that influence the gating decision (:issue:`2370`, :issue:`2393`, and
  :issue:`2425`)
* The waiver API is now documented (:issue:`2390`).
* The CLI and bindings can now paginate results when querying updates and overrides (:issue:`2405`).
* The ``bodhi`` CLI can now manage releases (:issue:`2419`).
* Comments have a mouse hoverover for timestamps (:commit:`60e2cddb`).
* The compose is now skipped if the repo is already staged (:commit:`9d94edb4`).
* Update statuses have a descriptive tooltip in the web UI (:commit:`40d04226`).
* A new ``/updates/{id}/get-test-results`` :doc:`../server_api/updates` API endpoint was added that
  can retrieve the test results for an update from Greenwave (:commit:`9631a9b6`).
* API users can specify which results they'd like to waive in the waiver API (:commit:`7d51ee54`).
* Update CI status is now displayed in the CLI (:commit:`4ab03afe`).
* The CLI can now waive test results (:commit:`833a9c14`).


Bug fixes
^^^^^^^^^

* Do not alter Bugzilla tickets that are not related to an approved product (:issue:`1043` and
  :issue:`2336`).
* Only comments after the most recent karma reset event are considered for critpath karma
  (:issue:`1996`).
* The homepage now uses correct link for critical path updates (:issue:`2094`).
* Bug and test case karma is now correctly registered (:issue:`2130`, :issue:`2189`, and
  :issue:`2456`).
* The web UI no longer uses a hardcoded Koji URL, and gets it from the new ``koji_web_url`` setting
  instead (:issue:`2182`).
* The Bodhi CLI will no longer reset unedited fields to their defaults when editing updates
  (:issue:`2208`).
* Return a helpful error when notes are not supplied when creating an update (:issue:`2214`).
* Removed a conflicting HTTPForbidden handler (:issue:`2258`).
* The RSS view for an update now works when the update has comments with no text (:issue:`2314`).
* Composes that fail the sanity check are now thrown out (:issue:`2374`).
* The uniqueness constraint on e-mail was dropped since it was not useful and did cause occasional
  problems (:issue:`2387`).
* e-mail templates are no longer hardcoded and are now stored on the filesystem (:issue:`2396`).
* Failure to act on private Bugzilla tickets is no longer logged at error level (:issue:`2431`).
* Block quotes are now correctly styled (:commit:`fd843a4e`).
* The validators will no longer report spurious errors due to previously failed validations
  (:commit:`5241205b`).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* Python 2 line test coverage was raised to 99% (:issue:`2409`).
* The development build system now implements the addTag and deleteTag calls (:commit:`4787a3ec`).
* The ``querystring`` validator is now used from Cornice (:commit:`f9900c05`).
* The tests now initialize the BodhiClient with a username so the tests will pass when there is a
  cached username (such as on a Fedora system that has Bodhi credentials) (:commit:`773232b6`).
* A new subclass of ``webtest.TestApp`` was created so tests would pass on Python 3
  (:commit:`847873f5`).
* ``devel/Vagrantfile.example`` was renamed to ``Vagrantfile`` (:commit:`e985fa3c`).
* The tests now pass on systems that don't use UTC (:commit:`63543675`).
* Python 3 line test coverage was significantly increased, up to 98%.
* A few warnings have been fixed.


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 3.9.0:

* Clement Verna
* Eli Young
* Lumir Balhar
* Mattia Verga
* Miro Hrončok
* Owen W. Taylor
* Patrick Uiterwijk
* Pierre-Yves Chibon
* Ralph Bean
* Vismay Golwala
* Randy Barlow


v3.8.1
------

Bugs
^^^^

* Fix two incompatibilities with Python 3.7 (:issue:`2436` and :issue:`2438`).


Contributor
^^^^^^^^^^^

Thanks to Miro Hrončok for fixing these issues.

Deprecation
^^^^^^^^^^^

* ``bodhi-manage-releases`` has been deprecated and will be removed in a future release. Please use
  ``bodhi releases`` instead (:issue:`2419`).


v3.8.0
------

Features
^^^^^^^^

* Container releases may now have a trailing "C" in their name (:issue:`2250`).
* The number of days an update has been in its current state is now displayed by the CLI
  (:issue:`2176` and :issue:`2269`).
* Composes are no longer batched by category (security vs. non-security, updates vs. testing)
  as this was not found to be beneficial and did slow the compose process down (:commit:`68c7936e`).
* A fedmsg is now transmitted when an update's time in testing is met (:commit:`99923f18`).
* New states for updates that are related to side tags have been documented (:commit:`d7b54323`).


Bugs
^^^^

* Bodhi no longer considers HTTP codes ``> 200`` and ``< 300`` to be errors (:issue:`2361`).
* Do not apply null Koji tags to ejected updates during compose (:issue:`2368`).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* The container composer has been refactored to use a cleaner helper function (:issue:`2259`).
* Bodhi's models now support side tags, a planned feature for an upcoming Bodhi release
  (:issue:`2275`).
* Compose.from_updates() returns a list in Python 3 (:issue:`2291`).
* Some silliness was removed from the universe, as ``bodhi.server.models.BodhiBase.get()`` no longer
  requires a database session to be passed to it (:issue:`2298`).
* The in-memory dogpile cache backend is used for development by default (:issue:`2300`).
* The CI container no longer installs Pungi, which speeds the CI testing time up (:issue:`2306`).
* Dropped support for ``str`` arguments from ``util.cmd()`` (:issue:`2332`).
* Python 3 line test coverage has increased to 85%.


Server upgrade instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

This update contains a migration to add two new updates states for side tags. After installing the
new server packages, you need to run the migrations::

    $ sudo -u apache /usr/bin/alembic -c /etc/bodhi/alembic.ini upgrade head


Contributors
------------

The following developers contributed to Bodhi 3.8.0:

* Mattia Verga
* Eli Young
* Lumir Balhar
* Patrick Uiterwijk
* Ralph Bean
* Paul W. Frields
* Randy Barlow


v3.7.0
------

Features
^^^^^^^^

* Include the missing tests in the summary about greenwave's decision
  (:issue:`2273` and :issue:`2345`).
* Show waivers about an update on its page for easier access to users and admins
  (:issue:`2277`).
* New ``legal_link`` and ``privacy_link`` settings allow Bodhi to link to a legal document and
  privacy policy (:issue:`2347`).


Bugs
^^^^
* Properly call the WaiverDB API when waiving tests from the UI (:issue:`2272`).
* Only ask greenwave about updates in active releases when asking their gating
  status (:issue:`2121`).
* Updates can no longer be pushed if they fail the gating tests (:issue:`2346`).


Contributors
------------

The following developers contributed to Bodhi 3.7.0:

* Pierre-Yves Chibon
* Patrick Uiterwijk
* Randy Barlow


v3.6.1
------

Bug fixes
^^^^^^^^^

* The update template no longer crashes on locked updates (:issue:`2288`).
* Do not cache calculated libravatar links (:issue:`2289`).
* Warm the release cache at startup to avoid intermingled queries (:issue:`2296`).
* Warm the home page cache at startup to avoid slow responses and intermingled queries
  (:issue:`2297`).
* Interpret the ``dogpile.cache.expiration_time`` as an ``int`` instead of a ``str``
  (:issue:`2299`).
* Do not cache the Koji latest candidates (:issue:`2301`).
* Do not require the web server to have Pungi installed since it does not use it (:issue:`2303`).


Contributors
^^^^^^^^^^^^

The following developers contributed patches to Bodhi 3.6.1:

* Patrick Uiterwijk
* Randy Barlow


v3.6.0
------

Deprecation
^^^^^^^^^^^

* ``bodhi-monitor-composes`` has been deprecated and will be removed in a future release. Please use
  ``bodhi composes list`` instead (:issue:`2170`).


Dependency changes
^^^^^^^^^^^^^^^^^^

* Pungi 4.1.20 or higher is now required.
* ``six`` is now a required dependency.
* Skopeo is now a required dependency for Bodhi installations that compose containers.


Features
^^^^^^^^

* The UI no longer lists a user's updates from retired releases by default (:issue:`752`).
* The CLI now supports update severity (:issue:`1814`).
* There is now a REST API to find out the status of running or failed composes (:issue:`2015`).
* The CLI now has a ``composes`` section which is able to query the server to display the status of
  composes (:issue:`2016`).
* Bodhi is now able to identify containers in Koji (:issue:`2027`).
* Bodhi is now able to compose containers (:issue:`2028`).
* There is now a ``cache_dir`` setting that can be used to direct Bodhi where to store a ``shelve``
  while generating metadata (:commit:`9b08f7be`).
* There is now documentation about buildroot overrides (:commit:`3450073c`).
* Bodhi will now include RPM changelogs in e-mails (:commit:`07b27fe8`).
* Bodhi's update e-mail now instruct ``dnf`` users to use the ``--advisory`` flag
  (:commit:`9fd56f99`).
* A new ``wait_for_repo_sig`` setting will allow Bodhi to work with signed repodata
  (:commit:`eea40394`).


Bugs
^^^^

* Bodhi will not reopen VERIFIED or CLOSED bugs anymore
  (:issue:`1091`, :issue:`1349`, :issue:`2168`).
* Bugzilla tickets will no longer get too much text inserted into their fixedin field
  (:issue:`1430`).
* The CLI --close-bugs flag now works correctly (:issue:`1818`).
* Fix ACL lookup for Module Packages (:issue:`2251`).
* Captcha errors are now correctly noted on cookies instead of the session, which was incompatible
  with Cornice 3 (:commit:`900e80a3`).
* The ``prefer_ssl`` setting now properly works (:commit:`9f55c7d2`).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* Uniqueness on a release's branch column was dropped, since container releases will likely use the
  same branch name as RPM releases (:issue:`2216`).
* Bodhi now learns the Pungi output dir directly from Pungi (:commit:`dbc337e5`).
* The composer now uses a semaphore to keep track of how many concurrent composes are running
  (:commit:`66f995e1`).
* CI tests are now also run against Fedora 28 (:issue:`2215`).
* Bodhi is now up to 98% line test coverage, from 95% in the 3.5.0 release.
* It is now possible to run the same tests that CI runs in the Vagrant environment by running
  ``devel/run_tests.sh``.
* The Bodhi CLI now supports Python 3 with 100% test coverage.
* The Bodhi server also now supports Python 3, but only has 78% test coverage with Python 3 as many
  tests need to be converted to pass on Python 3, thus it is not yet recommended to run Bodhi server
  on Python 3 even though it is theoretically possible.


Contributors
^^^^^^^^^^^^

The following developer contributed patches to Bodhi 3.6.0:

* Lumir Balhar
* Patrick Uiterwijk
* Mattia Verga
* Clément Verna
* Pierre-Yves Chibon
* Jan Kaluza
* Randy Barlow


v3.5.2
------

3.5.2 is an important bug fix release. Users are strongly recommended to use it over 3.5.1, which
introduced the bug.


Bug fix
^^^^^^^

* Fix loop variable leaking in sorted_updates, which led to packages not being tagged in Koji when
  they are pushed to a repository (:issue:`2243`).


Contributor
^^^^^^^^^^^

Thanks to Patrick Uiterwijk for submitting the fix for this release.


v3.5.1
------

3.5.1 inadvertently introduced a bug that caused packages not to be tagged properly in Koji. Users
are advised to skip this release and use 3.5.2 instead.


Bug fixes
^^^^^^^^^

* Use correct N, V, R splitting for module builds and add stream support (:issue:`2226`).
* Fixed Release.version_int for modular releases (:issue:`2232`).


Contributor
^^^^^^^^^^^

All 3.5.1 fixes were submitted by Patrick Uiterwijk.


v3.5.0
------

Feature
^^^^^^^

* Allow version-specific repomd url overrides (:issue:`2199`).


Bugs
^^^^

* The location of the release notes was fixed in the developer docs (:issue:`2154`).
* Use ":"'s instead of "-"'s as the NSV separator for Modules (:issue:`2167`).
* ``bodhi-push`` no longer authenticates to Koji (:issue:`2190`).
* Two tag references were fixed in ``bodhi-untag-branched`` (:commit:`59c83fc7`).
* Ensure there is a Greenwave summary to display before displaying it (:commit:`c07daf96`).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* The composer was refactored to split Pungi-specific code out into a new intermediate base class,
  to prepare the way for a coming container composer. This way the future container composer can
  share code with the RPM and Module composer code, while only using Pungi for the latter two
  (:issue:`2152`).
* The Vagrant development environment was upgraded to Fedora 27 (:issue:`2158`).


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 3.5.0:

* Patrick Uiterwijk
* Jan Kaluza
* Pierre-Yves Chibon
* Anatoli Babenia
* Randy Barlow


v3.4.0
------

Features
^^^^^^^^

* A UI for waiving failed test results has been added to the update page (:commit:`7f7472b6`).
* A man page was written for :doc:`man_pages/bodhi-untag-branched` (:commit:`2b83aeca`).
* ``bodhi-clean-old-mashes`` now prints directories before deleting them (:commit:`1cfa8a61`).


Bug fixes
^^^^^^^^^

* The mouseover text for severity was fixed on the new update form (:commit:`fe40e387`).
* It was made clearer in ``production.ini`` that some settings don't have defaults
  (:commit:`c865af96`).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* All of Bodhi's public code now has docblocks that follow PEP-257.


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 3.4.0:

* Matt Jia
* Lubomír Sedlář
* Randy Barlow


v3.3.0
------

Features
^^^^^^^^

* Test gating status is now polled whenever an update is created or edited (:issue:`1514`).
* Check the state of updates when they are missing signatures during ``bodhi-push`` (:issue:`1781`).
* There is now a web interface that displays the status of running composes (:issue:`2022`).
* There is now an API for waiving test results (:commit:`d52cc1a6`).
* The :doc:`update_states` are now documented (:commit:`6f4a48a4`).
* A :doc:`testing` doc was written (:commit:`f1f2d011`).
* A man page for :doc:`man_pages/bodhi-expire-overrides` was written (:commit:`e4402a32`).
* A man page for :doc:`man_pages/bodhi-manage-releases` was written (:commit:`84d01668`).
* Update status and request fields are now indexed for more performant searching
  (:commit:`768ccb6c`).
* ``updateinfo.xml`` now includes the severity level on security updates (:commit:`8c9c1bf9`).
* Only request the global_component field for critpath PDC lookups (:commit:`46f35882`).
* Newer updates are checked first by ``bodhi-check-policies`` (:commit:`c8942556`).


Bugs
^^^^

* Ensure that issued_date and updated_date are always present in metadata (:issue:`2137`).
* A link describing ffmarkdown syntax was fixed (:commit:`70895e52`).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* Some validation code was cleaned up to share code (:issue:`9f17b6cf`).
* The database now has a content type enum for containers (:issue:`2026`).
* Docblocks were written for more code.


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 3.3.0:

* Matt Jia
* Jonathan Lebon
* Yadnyawalkya Tale
* Patrick Uiterwijk
* Till Maas
* Ken Dreyer
* Randy Barlow


v3.2.0
------

Config change
^^^^^^^^^^^^^

The default value for ``greenwave_api_url`` was changed from
``https://greenwave.fedoraproject.org/api/v1.0`` to
``https://greenwave-web-greenwave.app.os.fedoraproject.org/api/v1.0`` as the old value was a
non-extant domain.


Dependency changes
^^^^^^^^^^^^^^^^^^

* Bodhi now requires ``cornice>=3`` (:issue:`1922`).
* pydns is no longer a dependency (:issue:`1959`).
* Bodhi now formally documents that it requires PostgreSQL >= 9.2.0 in :doc:`../administration`.
* Bodhi no longer requires ``progressbar``.


Features
^^^^^^^^

* There is now a man page for :doc:`man_pages/bodhi-dequeue-stable`.
* The composer backend no longer uses lock files, but instead stores its state in the database. This
  is a mix of feature, bug fix, and refactor. The feature is that there is now a
  :doc:`man_pages/bodhi-monitor-composes` CLI tool that allows admins to monitor the progress of
  running composes. This also fixed a few bugs in the process, such as allowing users to comment on
  updates while they are being composed. More than anything, it is a refactor as it allows us to add
  a compose management API which will enable Fedora to add container support to Bodhi in the future
  (:issue:`717`, :issue:`1245`, :issue:`2014`).


Bugs
^^^^

* Pending updates can no longer become batched and must wait until they've been composed into the
  testing repository (:issue:`1930`).
* The PDC critpath code was refactored to be more efficient and resilient (:issue:`2035`).
* A uniqueness constraint that was accidentally dropped for ``packages.{name,type}`` was added back
  (:issue:`2038`).
* The CLI help text was corrected to remove spaces between the list of builds in the example for
  creating multi-build updates (:issue:`2071`).
* Releases with no configured days in testing no longer crash Bodhi (:issue:`2076`).
* :doc:`man_pages/bodhi-check-policies` now also operates on pushed updates (:issue:`2085`).
* The client bindings' ``update_str()`` method was refactored and now does cleaner line wrapping
  (:commit:`3ef05fa9`).
* Do not fail the compose if there is an error when writing the changelog (:commit:`88fc8405`).
* Do not fail to write a changelog when Koji returns lists (:commit:`dc7546c0`).
* The composer now checkpoints adding comments, so they don't get sent twice if a compose is resumed
  after they were already sent (:commit:`03d87c98`).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* The link to the developer docs was corrected in the ``README`` file (:issue:`2044`).
* The :doc:`../developer/index` has been reorganized and is now easier to read (:commit:`243d278f`).
* There is now autogenerated documentation on the :doc:`../developer/models` (:commit:`7f8121a8`).
* ``builds.package_id`` is now non-nullable (:commit:`e87201fb`).
* ``updates.release_id`` is now non-nullable (:commit:`5371bbd1`).
* Much progress was made towards Python 3 support.
* Docblocks were written for many more modules.
* Line test coverage is now up to 95%.
* Some unused and unreachable code was removed.
* The devbuildsys now supports el6 and el7 builds.


Contributors
^^^^^^^^^^^^

The following developers contributed to Bodhi 3.2.0:

* Chenxiong Qi
* Lumir Balhar
* Matt Jia
* Patrick Uiterwijk
* Till Maas
* Randy Barlow


v3.1.0
------

Special instructions
^^^^^^^^^^^^^^^^^^^^

* The Alembic configuration file has changed to use the Python path of the migrations.
  In order to run the new migrations, you should ensure your alembic.ini has
  ``script_location = bodhi:server/migrations``.


Dependency changes
^^^^^^^^^^^^^^^^^^

* The client formally depends on ``iniparse`` now. It needed this before but the dependency was
  undocumented (:commit:`ddf47eb2`).
* Bodhi no longer uses or requires ``webhelpers``. RSS feeds are now generated by ``feedgen``, a new
  required dependency.
* Bodhi no longer uses or requires ``bunch``.


Features
^^^^^^^^

* The CLI now prints a helpful hint about how to use ``koji wait-repo`` when creating or editing a
  buildroot override, or when a query for overrides returns exactly one result (:issue:`1376`).
* Bodhi now uses connection pooling when making API requests to other services (:issue:`1753`).
* The bindings now conditionally import ``dnf`` (:issue:`1812`).
* It is now possible to query for Releases by a list of primary keys, by using the querystring
  ``ids`` with the ``releases/`` API.
* Builds now serialize their ``release_id`` field.
* It is now possible to configure a maximum number of mash threads that Bodhi will run at once,
  which is handy if the new Pungi masher has been mean to your NAS. There is a new
  ``max_concurrent_mashes`` setting in production.ini, which defaults to ``2``.
* There is now a man page for :doc:`man_pages/bodhi-clean-old-mashes`.
* The documentation was reorganized by type of reader (:commit:`14e81a81`).
* The documentation now uses the Alabaster theme (:commit:`f15351e2`).
* The CLI now has a ``--arch`` flag that can be used when downloading updates to specify which
  architecture is desired (:commit:`6538c9e9`).
* Bodhi's documentation now includes an :doc:`../administration` section which includes
  documentation on its various settings (:commit:`310f56d4`).


Bugs
^^^^

* Bodhi now uses the correct comment on critical path updates regarding how many days are required
  in testing (:issue:`1361`).
* All home page update types now have mouseover titles (:issue:`1620`).
* e-mail subjects again include the version of the updates (:issue:`1635`).
* The bindings will re-attempt authentication upon captcha failures (:issue:`1787`).
* The formatting is fixed on mobile for the edit/create update form (:issue:`1791`).
* The "Push to Stable" button is now rendered in the web UI on batched updates (:issue:`1907`).
* Do not fail the mash if a changelog is malformed (:issue:`1989`).
* :doc:`man_pages/bodhi-dequeue-stable` no longer dies if it encounters updates that can't be pushed
  stable (:issue:`2004`).
* Unreachable RSS Accept-header based redirects were fixed (:commit:`6f3db0c0`).
* Fixed an unsafe default in ``bodhi.server.util.call_api()`` (:commit:`9461b3a4`).
* Bodhi now distinguishes between testing and stable when asking Greenwave for gating decisions
  (:commit:`6d907a7a`).
* The CLI now renders the correct URL for updates without aliases (:commit:`caaa0e6e`).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* The database migrations are now shipped as part of the Python distribution
  (`#1777 <https://github.com/fedora-infra/bodhi/pull/1777>`_).
* The developer docs pertaining to using virtualenvs have been corrected and improved
  (:issue:`1797`).
* The ``test_utils.py`` tests now use the ``BaseTestCase``, which allows them to pass when run by
  themselves (:issue:`1817`).
* An obsolete mash check for symlinks was removed (:issue:`1819`).
* A mock was moved inside of a test to avoid inter-test dependencies (:issue:`1848`).
* Bodhi is now compliant with ``flake8``'s ``E722`` check (:issue:`1927`).
* The JJB YAML file is now tested to ensure it is valid YAML (:issue:`1934`).
* Some code has been prepared for Python 3 compatibility (:commit:`d7763560`).
* Developers are now required to sign the `DCO`_ (:commit:`34d0ceb0`).
* There is now formal documentation on how to submit patches to Bodhi (:commit:`bb20a0ee`).
* Bodhi is now tested by Fedora containers in the CentOS CI environment (:commit:`36d603f0`).
* Bodhi is now tested against dependencies from PyPI (:commit:`1e8fb65d`).
* The ``development.ini.example`` file has been reduced to a minimal form, which means we no longer
  need to document the settings in two places (:commit:`2b7dc4e5`).
* Bodhi now runs CI tests for different PRs in parallel (:commit:`6427309f`).
* ``Vagrantfile.example`` has been moved to ``devel/`` for tidiness (:commit:`21ff2e58`).
* It is now easier to replicate the CI environment locally by using the ``devel/run_tests.sh``
  script.
* Many more docblocks have been written across the codebase.
* Line test coverage is now at 93%.


.. _DCO: https://developercertificate.org/


Release contributors
^^^^^^^^^^^^^^^^^^^^

The following developers contributed to Bodhi 3.1.0:

* Alena Volkova
* Aman Sharma
* Caleigh Runge-Hottman
* Dusty Mabe
* František Zatloukal
* Jeremy Cline
* Ken Dreyer
* Lumir Balhar
* Martin Curlej
* Patrick Uiterwijk
* Pierre-Yves Chibon
* Ralph Bean
* Ryan Lerch
* Randy Barlow


3.0.0
-----

Backwards incompatible changes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* Support for the ``USERNAME`` environment variable in all of Bodhi's CLI tools has been dropped, as
  it conflicts with GDM's variable by the same name. Many users do not have the same FAS username as
  they use on their desktop, and this variable causes confusion in the CLI
  (`#1789 <https://github.com/fedora-infra/bodhi/issues/1789>`_).
* The layout of the repositories after mash is now different.
* The following settings have been removed from Bodhi, as Pungi now manages
  comps files instead of Bodhi::

    * ``compose_atomic_trees``
    * ``comps_dir``
    * ``comps_url``
    * ``mash_conf``

* ``bodhi-push`` no longer has a ``--staging`` flag as it was not needed. It was used to determine
  the mashing directory to look for lock files, but the directories it looked in were hardcoded
  instead of using the ``mash_dir`` setting. With 3.0.0, ``mash_dir`` is used and the ``--staging``
  flag is no longer needed.


Dependency changes
^^^^^^^^^^^^^^^^^^

* Bodhi no longer uses or requires mash.
* Bodhi no longer uses or requires fedmsg-atomic-composer.
* Pungi is now a required dependency for Bodhi, replacing mash.
* jinja2 is now a required dependency for Bodhi, used by its masher.


New settings
^^^^^^^^^^^^

The ``production.ini`` file supports some new settings:

* ``pungi.basepath`` specifies which path Bodhi should find Pungi config files inside. Defaults to
  ``/etc/bodhi``.
* ``pungi.cmd`` specifies the command to run ``pungi`` with. Defaults to ``/usr/bin/pungi-koji``.
* ``pungi.conf.module`` should be the name of a jinja2 template file found in ``pungi.basepath``
  that will be rendered to generate a Pungi config file that will be used to mash RPM repositories
  (yum, dnf, and atomic repositories). Defaults to ``pungi.module.conf``, meaning that an
  ``/etc/bodhi/pungi.module.conf`` is the default config file for Modules.
* ``pungi.conf.rpm`` should be the name of a jinja2 template file found in ``pungi.basepath`` that
  will be rendered to generate a Pungi config file that will be used to mash RPM repositories (yum,
  dnf, and atomic repositories). Defaults to ``pungi.rpm.conf``, meaning that an
  ``/etc/bodhi/pungi.rpm.conf`` is the default config file for RPMs.
* The ``pungi.conf.*`` setting files above have the following jinja2 template variables available to
  them::

    * 'id': The id of the Release being mashed.
    * 'release': The Release being mashed.
    * 'request': The request being mashed.
    * 'updates': The Updates being mashed.

You will need to create ``variants.xml`` templates inside ``pungi.basepath`` as well. These
templates will have access to the same template variables described above, and should be named
``variants.rpm.xml.j2`` and ``variants.module.xml.j2``, for RPM composes and module composes,
respectively.


Features
^^^^^^^^

The 3.0.0 release is focused on delivering one big change that enables a variety of features: the
use of Pungi to do mashing rather than mash. The most notable feature this enables is the ability to
deliver update repositories for modules, but in general all of Pungi's feature set is now available
for Bodhi to use.

* Bodhi now supports non-RPM artifacts, namely, modules
  (`#653 <https://github.com/fedora-infra/bodhi/issues/653>`_,
  `#1330 <https://github.com/fedora-infra/bodhi/issues/1330>`_).
* Via Pungi, Bodhi is now able to use Koji signed repos
  (`#909 <https://github.com/fedora-infra/bodhi/issues/909>`_).
* Via Pungi, Bodhi is now able to generate OSTrees that are more consistent with Fedora's release
  day OSTrees
  (`#1182 <https://github.com/fedora-infra/bodhi/issues/1182>`_).
* Bodhi now uses Pungi instead of the retiring mash project
  (`#1219 <https://github.com/fedora-infra/bodhi/issues/1219>`_).


Bugs
^^^^

* Bodhi, via Pungi, will now reliably produce repomd files
  (`#887 <https://github.com/fedora-infra/bodhi/issues/887>`_).
* Bodhi's CLI no longer uses USERNAME, which conflicted with GDM for users who use a different local
  system username than their FAS username. For such users, there was no workaround other than to
  constantly use the ``--user`` flag, and the environment varaible wasn't particularly useful
  anymore now that the Bodhi CLI remembers usernames after one successful authentication
  (`#1789 <https://github.com/fedora-infra/bodhi/issues/1789>`_).


Release contributors
^^^^^^^^^^^^^^^^^^^^

The following developers contributed to Bodhi 3.0.0:

* Patrick Uiterwijk
* Adam Miller
* Dusty Mabe
* Kushal Das
* Randy Barlow


2.12.2
------

Bugs
^^^^

* Positive karma on stable updates no longer sends them back to batched
  (`#1881 <https://github.com/fedora-infra/bodhi/issues/1881>`_).
* Push to batched buttons now appear on pushed updates when appropriate
  (`#1875 <https://github.com/fedora-infra/bodhi/issues/1875>`_).


Release contributors
^^^^^^^^^^^^^^^^^^^^

The following developers contributed to Bodhi 2.12.2:

* Randy Barlow


2.12.1
------

Bugs
^^^^

* Use separate directories to clone the comps repositories
  (`#1885 <https://github.com/fedora-infra/bodhi/pull/1885>`_).


Release contributors
^^^^^^^^^^^^^^^^^^^^

The following developers contributed to Bodhi 2.12.1:

* Patrick Uiterwijk
* Randy Barlow


2.12.0
------

Features
^^^^^^^^

* Bodhi now asks Pagure to expand group membership when Pagure is used for ACLs
  (`#1810 <https://github.com/fedora-infra/bodhi/issues/1810>`_).
* Bodhi now displays Atomic CI pipeline results
  (`#1847 <https://github.com/fedora-infra/bodhi/pull/1847>`_).


Bugs
^^^^

* Use generic superclass models where possible
  (`#1793 <https://github.com/fedora-infra/bodhi/issues/1793>`_).


Release contributors
^^^^^^^^^^^^^^^^^^^^

The following developers contributed to Bodhi 2.12.0:

* Pierre-Yves Chibon
* Randy Barlow


2.11.0
------

Features
^^^^^^^^

* Bodhi now batches non-urgent updates together for less frequent churn. There is a new
  ``bodhi-dequeue-stable`` CLI that is intended be added to cron that looks for batched updates and
  moves them to stable
  (`#1157 <https://github.com/fedora-infra/bodhi/issues/1157>`_).


Bugs
^^^^

* Improved bugtracker linking in markdown input
  (`#1406 <https://github.com/fedora-infra/bodhi/issues/1406>`_).
* Don't disable autopush when the update is already requested for stable
  (`#1570 <https://github.com/fedora-infra/bodhi/issues/1570>`_).
* There is now a timeout on fetching results from ResultsDB in the backend
  (`#1597 <https://github.com/fedora-infra/bodhi/issues/1597>`_).
* Critical path updates now have positive days_to_stable and will only comment about pushing to
  stable when appropriate
  (`#1708 <https://github.com/fedora-infra/bodhi/issues/1708>`_).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* More docblocks have been written.


Release contributors
^^^^^^^^^^^^^^^^^^^^

The following developers contributed to Bodhi 2.11.0:

* Caleigh Runge-Hottman
* Ryan Lerch
* Rimsha Khan
* Randy Barlow


2.10.1
------

Bug fixes
^^^^^^^^^

* Adjust the Greenwave subject query to include the original NVR of the builds
  (`#1765 <https://github.com/fedora-infra/bodhi/pull/1765>`_).


Release contributors
^^^^^^^^^^^^^^^^^^^^

The following developers contributed to Bodhi 2.10.1:

* Ralph Bean


2.10.0
------

Compatibility changes
^^^^^^^^^^^^^^^^^^^^^

This release of Bodhi has a few changes that are technically backward incompatible in some senses,
but it was determined that each of these changes are justified without raising Bodhi's major
version, often due to features not working at all or being unused. Justifications for each are given
inline.

* dnf and iniparse are now required dependencies for the Python bindings. Justification:
  Technically, these were needed before for some of the functionality, and the bindings would
  traceback if that functionality was used without these dependencies being present. With this
  change, the module will fail to import without them, and they are now formal dependencies.
* Support for EL 5 has been removed in this release. Justification: EL 5 has become end of life.
* The pkgtags feature has been removed. Justification: It did not work correctly and enabling it was
  devastating
  (`#1634 <https://github.com/fedora-infra/bodhi/issues/1634>`_).
* Some bindings code that could log into Koji with TLS certificates was removed. Justification: It
  was unused
  (`b4474676 <https://github.com/fedora-infra/bodhi/commit/b4474676>`_).
* Bodhi's short-lived ``ci_gating`` feature has been removed, in favor of the new
  Greenwave integration feature. Thus, the ``ci.required`` and ``ci.url`` settings no longer
  function in Bodhi. The ``bodhi-babysit-ci`` utility has also been removed. Justification: The
  feature was never completed and thus no functionality is lost
  (`#1733 <https://github.com/fedora-infra/bodhi/pull/1733>`_).


Features
^^^^^^^^

* There are new search endpoints in the REST API that perform ilike queries to support case
  insensitive searching. Bodhi's web interface now uses these endpoints
  (`#997 <https://github.com/fedora-infra/bodhi/issues/997>`_).
* It is now possible to search by update alias in the web interface
  (`#1258 <https://github.com/fedora-infra/bodhi/issues/1258>`_).
* Exact matches are now sorted first in search results
  (`#692 <https://github.com/fedora-infra/bodhi/issues/692>`_).
* The CLI now has a ``--mine`` flag when searching for updates or overrides
  (`#811 <https://github.com/fedora-infra/bodhi/issues/811>`_,
  `#1382 <https://github.com/fedora-infra/bodhi/issues/1382>`_).
* The CLI now has more search parameters when querying overrides
  (`#1679 <https://github.com/fedora-infra/bodhi/issues/1679>`_).
* The new case insensitive search is also used when hitting enter in the search box in the web UI
  (`#870 <https://github.com/fedora-infra/bodhi/issues/870>`_).
* Bodhi is now able to query Pagure for FAS groups for ACL info
  (`f9414601 <https://github.com/fedora-infra/bodhi/commit/f9414601>`_).
* The Python bindings' ``candidates()`` method now automatically intiializes the username
  (`6e8679b6 <https://github.com/fedora-infra/bodhi/commit/6e8679b6>`_).
* CLI errors are now printed in red text
  (`431b9078 <https://github.com/fedora-infra/bodhi/commit/431b9078>`_).
* The graphs on the metrics page now have mouse hovers to indicate numerical values
  (`#209 <https://github.com/fedora-infra/bodhi/issues/209>`_).
* Bodhi now has support for using `Greenwave <https://pagure.io/greenwave/>`_ to gate updates based
  on test results. See the new ``test_gating.required``, ``test_gating.url``, and
  ``greenwave_api_url`` settings in ``production.ini`` for details on how to enable it. Note also
  that this feature introduces a new server CLI tool, ``bodhi-check-policies``, which is intended to
  be run via cron on a regular interval. This CLI tool communicates with Greenwave to determine if
  updates are passing required tests or not
  (`#1733 <https://github.com/fedora-infra/bodhi/pull/1733>`_).


Bug fixes
^^^^^^^^^

* The autokarma check box's value now persists when editing updates
  (`#1692 <https://github.com/fedora-infra/bodhi/issues/1692>`_,
  `#1482 <https://github.com/fedora-infra/bodhi/issues/1482>`_, and
  `#1308 <https://github.com/fedora-infra/bodhi/issues/1308>`_).
* The CLI now catches a variety of Exceptions and prints user readable errors instead of tracebacks
  (`#1126 <https://github.com/fedora-infra/bodhi/issues/1126>`_,
  `#1626 <https://github.com/fedora-infra/bodhi/issues/1626>`_).
* The Python bindings' ``get_releases()`` method now uses a GET request
  (`#784 <https://github.com/fedora-infra/bodhi/issues/784>`_).
* The HTML sanitization code has been refactored, which fixed a couple of issues where Bodhi didn't
  correctly escape things like e-mail addresses
  (`#1656 <https://github.com/fedora-infra/bodhi/issues/1656>`_,
  `#1721 <https://github.com/fedora-infra/bodhi/issues/1721>`_).
* The bindings' docstring for the ``comment()`` method was corrected to state that the ``email``
  parameter is used to make anonymous comments, rather than to enable or disable sending of e-mails
  (`#289 <https://github.com/fedora-infra/bodhi/issues/289>`_).
* The web interface now links directly to libravatar's login page instead of POSTing to it
  (`#1674 <https://github.com/fedora-infra/bodhi/issues/1674>`_).
* The new/edit update form in the web interface now works with the new typeahead library
  (`#1731 <https://github.com/fedora-infra/bodhi/issues/1731>`_).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* Several more modules have been documented with PEP-257 compliant docblocks.
* Several new tests have been added to cover various portions of the code base, and Bodhi now has
  89% line test coverage. The goal is to reach 100% line coverage within the next 12 months, and
  then begin to work towards 100% branch coverage.


Release contributors
^^^^^^^^^^^^^^^^^^^^

The following developers contributed to Bodhi 2.10.0:

* Ryan Lerch
* Matt Jia
* Matt Prahl
* Jeremy Cline
* Ralph Bean
* Caleigh Runge-Hottman
* Randy Barlow


2.9.1
-----

2.9.1 is a security release for
`CVE-2017-1002152 <https://github.com/fedora-infra/bodhi/issues/1740>`_.

Release contributors
^^^^^^^^^^^^^^^^^^^^

Thanks to Marcel for reporting the issue. Randy Barlow wrote the fix.


2.9.0
-----

Features
^^^^^^^^

* It is now possible to set required Taskotron tests with the ``--requirements`` CLI flag
  (`#1319 <https://github.com/fedora-infra/bodhi/issues/1319>`_).
* The CLI now has tab completion in bash
  (`#1188 <https://github.com/fedora-infra/bodhi/issues/1188>`_).
* Updates that are pending testing now go straight to stable if they reach required karma
  (`#632 <https://github.com/fedora-infra/bodhi/issues/632>`_).
* The automated tests tab now shows a count on info results
  (`1de12f6a <https://github.com/fedora-infra/bodhi/commit/1de12f6a>`_).
* The UI now displays a spinner while a search is in progress
  (`#436 <https://github.com/fedora-infra/bodhi/issues/436>`_).
* It is now possible to middle click on search results in the web UI
  (`#461 <https://github.com/fedora-infra/bodhi/issues/461>`_).
* Pending releases are now displayed on the home page
  (`#1619 <https://github.com/fedora-infra/bodhi/issues/1619>`_).
* Links without an explicit scheme can now be detected as links
  (`#1721 <https://github.com/fedora-infra/bodhi/issues/1721>`_).


Bugs
^^^^

* Wiki test cases are no longer duplicated
  (`#780 <https://github.com/fedora-infra/bodhi/issues/780>`_).
* The server bodhi-manage-releases script now uses the new Bodhi bindings
  (`#1338 <https://github.com/fedora-infra/bodhi/issues/1338>`_).
* The server bodhi-manage-releases script now supports the ``--url`` flag
  (`0181a344 <https://github.com/fedora-infra/bodhi/commit/0181a344>`_).
* The ``--help`` output from the Bodhi CLI is cleaner and more informative
  (`#1457 <https://github.com/fedora-infra/bodhi/issues/1457>`_).
* The CLI now provides more informative error messages when creating duplicate overrides
  (`#1377 <https://github.com/fedora-infra/bodhi/issues/1377>`_).
* E-mail subjects now include build versions again
  (`#1635 <https://github.com/fedora-infra/bodhi/issues/1635>`_).
* Taskotron results with the same scenario key are now all displayed
  (`d5b0bfa3 <https://github.com/fedora-infra/bodhi/commit/d5b0bfa3>`_).
* The front page UI elements now line up
  (`#1659 <https://github.com/fedora-infra/bodhi/issues/1659>`_).
* The UI now properly urlencodes search URLs to properly escape characters such as "+"
  (`#1015 <https://github.com/fedora-infra/bodhi/issues/1015>`_).
* e-mail addresses are now properly processed by the markdown system
  (`#1656 <https://github.com/fedora-infra/bodhi/issues/1656>`_).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* The bundled typeahead JavaScript library is rebased to version 1.1.1 from the maintained
  fork at https://github.com/corejavascript/typeahead.js . The main typeahead repo
  appears to be unmaintained and contained a bug that we were hitting:
  https://github.com/twitter/typeahead.js/issues/1381
* Docblocks were written for several more modules.
* Bodhi now hard depends on rpm instead of conditionally importing it
  (`#1166 <https://github.com/fedora-infra/bodhi/issues/1166>`_).
* Bodhi now has CI provided by CentOS that is able to test pull requests. Thanks to Brian Stinson
  and CentOS for providing this service to the Bodhi project!
* Some ground work has been done in order to enable batched updates, so that medium and low priority
  updates can be pushed on a less frequent interval than high priority (security or urgent) updates.
* Bodhi now uses py.test as the test runner instead of nose.
* Tox is now used to run the style tests.
* There is now a unified test base class that creates a single TestApp for the tests to use. The
  TestApp was the source of a significant memory leak in Bodhi's tests. As a result of this
  refactor, Bodhi's tests now consume about 450 MB instead of about 4.5 GB. As a result, the example
  Vagrantfile now uses 2 GB of RAM instead of 5 GB. It is likely possible to squeeze it down to 1 GB
  or so, if desired.
* Bodhi now supports both the bleach 1 and bleach 2 APIs
  (`#1718 <https://github.com/fedora-infra/bodhi/issues/1718>`_).


Release contributors
^^^^^^^^^^^^^^^^^^^^

The following developers contributed to Bodhi 2.9.0:

* Ryan Lerch
* Jeremy Cline
* Clement Verna
* Caleigh Runge-Hottman
* Kamil Páral
* Brian Stinson
* Martin Curlej
* Trishna Guha
* Brandon Gray
* Randy Barlow


2.8.1
-----

Bugs
^^^^

* Restore defaults for three settings back to the values they had in Bodhi 2.7.0 (
  `#1633 <https://github.com/fedora-infra/bodhi/pull/1633>`_,
  `#1640 <https://github.com/fedora-infra/bodhi/pull/1640>`_, and
  `#1641 <https://github.com/fedora-infra/bodhi/pull/1641>`_).


Release contributors
^^^^^^^^^^^^^^^^^^^^

The following contributors submitted patches for Bodhi 2.8.1:

* Patrick Uiterwijk (the true 2.8.1 hero)
* Randy Barlow


2.8.0
-----

Special instructions
^^^^^^^^^^^^^^^^^^^^

* There is a new setting, ``ci.required`` that defaults to False. If you wish to use CI, you must
  add a cron task to call the new ``bodhi-babysit-ci`` CLI periodically.


Deprecation
^^^^^^^^^^^

The ``/search/packages`` API call has been deprecated.


New Dependencies
^^^^^^^^^^^^^^^^

* Bodhi now uses Bleach to sanitize markdown input from the user.
  python-bleach 1.x is a new dependency in this release of Bodhi.


Features
^^^^^^^^

* The API, fedmsg messages, bindings, and CLI now support non-RPM content (
  `#1325 <https://github.com/fedora-infra/bodhi/issues/1325>`_,
  `#1326 <https://github.com/fedora-infra/bodhi/issues/1326>`_,
  `#1327 <https://github.com/fedora-infra/bodhi/issues/1327>`_, and
  `#1328 <https://github.com/fedora-infra/bodhi/issues/1328>`_).
  Bodhi now knows about Fedora's new module format, and is able to handle everything they need
  except publishing (which will appear in a later release). This release is also the first Bodhi
  release that is able to handle multiple content types.
* Improved OpenQA support in the web UI
  (`#1471 <https://github.com/fedora-infra/bodhi/issues/1471>`_).
* The type icons are now aligned in the web UI
  (`4b6b7597 <https://github.com/fedora-infra/bodhi/commit/4b6b7597>`_ and
  `d0940323 <https://github.com/fedora-infra/bodhi/commit/d0940323>`_).
* There is now a man page for ``bodhi-approve-testing``
  (`cf8d897f <https://github.com/fedora-infra/bodhi/commit/cf8d897f>`_).
* Bodhi can now automatically detect whether to use DDL table locks if BDR is present during
  migrations (`059b5ab7 <https://github.com/fedora-infra/bodhi/commit/059b5ab7>`_).
* Locked updates now grey out the edit buttons with a tooltip to make the lock more obvious to the
  user (`#1492 <https://github.com/fedora-infra/bodhi/issues/1492>`_).
* Users can now do multi-line literal code blocks in comments
  (`#1509 <https://github.com/fedora-infra/bodhi/issues/1509>`_).
* The web UI now has more descriptive placeholder text
  (`1a7122cd <https://github.com/fedora-infra/bodhi/commit/1a7122cd>`_).
* All icons now have consistent width in the web UI
  (`6dfe6ff3 <https://github.com/fedora-infra/bodhi/commit/6dfe6ff3>`_).
* The front page has a new layout
  (`6afb6b07 <https://github.com/fedora-infra/bodhi/commit/6afb6b07>`_).
* Bodhi is now able to use Pagure and PDC as sources for ACL and package information
  (`59551861 <https://github.com/fedora-infra/bodhi/commit/59551861>`_).
* Bodhi's configuration loader now validates all values and centralizes defaults. Thus, it is now
  possible to comment most of Bodhi's settings file and achieve sane defaults. Some settings are
  still required, see the default ``production.ini`` file for documentation of all settings and
  their defaults. A few unused settings were removed
  (`#1488 <https://github.com/fedora-infra/bodhi/issues/1488>`_,
  `#1489 <https://github.com/fedora-infra/bodhi/issues/1489>`_, and
  `263b7b7f <https://github.com/fedora-infra/bodhi/commit/263b7b7f>`_).
* The web UI now displays the content type of the update
  (`#1329 <https://github.com/fedora-infra/bodhi/issues/1329>`_).
* Bodhi now has a new ``ci.required`` setting that defaults to False. If enabled. updates will gate
  based on Continuous Integration test results and will not proceed to updates-testing unless the
  tests pass
  (`0fcb73f8 <https://github.com/fedora-infra/bodhi/commit/0fcb73f8>`_).
* Update builds are now sorted by NVR
  (`#1441 <https://github.com/fedora-infra/bodhi/issues/1441>`_).
* The backend code is reworked to allow gating on resultsdb data and requirement validation
  performance is improved
  (`#1550 <https://github.com/fedora-infra/bodhi/issues/1550>`_).
* Bodhi is now able to map distgit commits to Builds, which helps map CI results to Builds. There is
  a new ``bodhi-babysit-ci`` CLI that must be run periodically in cron if ``ci.required`` is
  ``True``
  (`ae01e5d1 <https://github.com/fedora-infra/bodhi/commit/ae01e5d1>`_).


Bugs
^^^^

* A half-hidden button is now fully visible on mobile devices
  (`#1467 <https://github.com/fedora-infra/bodhi/issues/1467>`_).
* The signing status is again visible on the update page
  (`#1469 <https://github.com/fedora-infra/bodhi/issues/1469>`_).
* The edit update form will not be presented to users who are not auth'd
  (`#1521 <https://github.com/fedora-infra/bodhi/issues/1521>`_).
* The CLI ``--autokarma`` flag now works correctly
  (`#1378 <https://github.com/fedora-infra/bodhi/issues/1378>`_).
* E-mail subjects are now shortened like the web UI titles
  (`#882 <https://github.com/fedora-infra/bodhi/issues/882>`_).
* The override editing form is no longer displayed unless the user is logged in
  (`#1541 <https://github.com/fedora-infra/bodhi/issues/1541>`_).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* Several more modules now pass pydocstyle PEP-257 tests.
* The development environment has a new ``bshell`` alias that sets up a usable Python shell,
  initialized for Bodhi.
* Lots of warnings from the unit tests have been fixed.
* The dev environment cds to the source folder upon ``vagrant ssh``.
* There is now a ``bfedmsg`` development alias to see fedmsgs.
* A new ``bresetdb`` development alias will reset the database to the same state as when
  ``vagrant up`` completed.
* Some unused code was removed
  (`afe5bd8c <https://github.com/fedora-infra/bodhi/commit/afe5bd8c>`_).
* Test coverage was raised significantly, from 85% to 88%.
* The development environment now has httpie by default.
* The default Vagrant memory was raised
  (`#1588 <https://github.com/fedora-infra/bodhi/issues/1588>`_).
* Bodhi now has a Jenkins Job Builder template for use with CentOS CI.
* A new ``bdiff-cover`` development alias helps compare test coverage in current branch to the
  ``develop`` branch, and will alert the developer if there are any lines missing coverage.


Release contributors
^^^^^^^^^^^^^^^^^^^^

The following developers contributed to Bodhi 2.8.0:

* Ryan Lerch
* Ralph Bean
* Pierre-Yves Chibon
* Matt Prahl
* Martin Curlej
* Adam Williamson
* Kamil Páral
* Clement Verna
* Jeremy Cline
* Matthew Miller
* Randy Barlow


2.7.0
-----

Features
^^^^^^^^

* The bodhi CLI now supports editing an override.
  (`#1049 <https://github.com/fedora-infra/bodhi/issues/1049>`_).
* The Update model is now capable of being associated with different Build types
  (`#1394 <https://github.com/fedora-infra/bodhi/issues/1394>`_).
* The bodhi CLI now supports editing an update using the update alias.
  (`#1409 <https://github.com/fedora-infra/bodhi/issues/1409>`_).
* The web UI now uses Fedora 26 in its example text instead of Fedora 20
  (`ec0c619a <https://github.com/fedora-infra/bodhi/commit/ec0c619a>`_).
* The Build model is now polymorphic to support non-RPM content
  (`#1393 <https://github.com/fedora-infra/bodhi/issues/1393>`_).


Bugs
^^^^

* Correctly calculate days to stable for critical path updates
  (`#1386 <https://github.com/fedora-infra/bodhi/issues/1386>`_).
* Bodhi now logs some messages at info instead of error
  (`#1412 <https://github.com/fedora-infra/bodhi/issues/1412>`_).
* Only show openQA results since last update modification
  (`#1435 <https://github.com/fedora-infra/bodhi/issues/1435>`_).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* SQL queries are no longer logged by default.
* fedmsgs are now viewable in the development environment.
* There is a new test to ensure there is only one Alembic head.
* There is a new bash alias, bteststyle, that runs the code style tests.
* The BuildrootOverride model is now documented.


Release contributors
^^^^^^^^^^^^^^^^^^^^

The following contributors submitted patches for Bodhi 2.7.0:

* Clement Verna
* Jeremy Cline
* Bianca Nenciu
* Caleigh Runge-Hottman
* Adam Williamson
* Robert Scheck
* Ryan Lerch
* Randy Barlow


2.6.2
-----

This release focused on CLI authentication issues. One of the issues requires users to also update
their python-fedora installation to at least 0.9.0.


Bugs
^^^^

* The CLI is now able to appropriately handle expiring sessions
  (`#1474 <https://github.com/fedora-infra/bodhi/issues/1474>`_).
* The CLI now only prompts for a password when needed
  (`#1500 <https://github.com/fedora-infra/bodhi/pull/1500>`_).
* Don't traceback if the user doesn't use the ``--user`` flag
  (`#1505 <https://github.com/fedora-infra/bodhi/pull/1505>`_).


Release contributors
^^^^^^^^^^^^^^^^^^^^

The following contributors submitted patches for Bodhi 2.6.2:

* Randy Barlow


2.6.1
-----

This release fixes 4 issues with three commits.


Bugs
^^^^

* Web requests now use the correct session for transactions
  (`#1470 <https://github.com/fedora-infra/bodhi/issues/1470>`_,
  `#1473 <https://github.com/fedora-infra/bodhi/issues/1473>`_).
* fedmsgs are now converted to dictionaries before queuing
  (`#1472 <https://github.com/fedora-infra/bodhi/issues/1472>`_).
* Error messages are still logged if rolling back the transaction raises an Exception
  (`#1475 <https://github.com/fedora-infra/bodhi/issues/1475>`_).


Release contributors
^^^^^^^^^^^^^^^^^^^^

The following contributors submitted patches for Bodhi 2.6.1:

* Jeremy Cline
* Randy Barlow


2.6.0
-----

Special instructions
^^^^^^^^^^^^^^^^^^^^

#. The database migrations have been trimmed in this release. To upgrade to this version of Bodhi
   from a version prior to 2.3, first upgrade to Bodhi 2.3, 2.4, or 2.5, run the database
   migrations, and then upgrade to this release.
#. Bodhi cookies now expire, but cookies created before 2.6.0 will not automatically expire. To
   expire all existing cookies so that only expiring tickets exist, you will need to change
   ``authtkt.secret`` to a new value in your settings file.


Dependency adjustments
^^^^^^^^^^^^^^^^^^^^^^

* zope.sqlalchemy is no longer a required dependency
  (`#1414 <https://github.com/fedora-infra/bodhi/pull/1414>`_).
* WebOb is no longer a directly required dependency, though it is still indirectly required through
  pyramid.


Features
^^^^^^^^

* The web UI footer has been restyled to fit better with the new theme
  (`#1366 <https://github.com/fedora-infra/bodhi/pull/1366>`_).
* A link to documentation has been added to the web UI footer
  (`#1321 <https://github.com/fedora-infra/bodhi/issues/1321>`_).
* The bodhi CLI now supports editing updates
  (`#937 <https://github.com/fedora-infra/bodhi/issues/937>`_).
* The CLI's ``USERNAME`` environment variable is now documented, and its ``--user`` flag is
  clarified (`28dd380a <https://github.com/fedora-infra/bodhi/commit/28dd380a>`_).
* The icons that we introduced in the new theme previously didn't have titles.
  Consequently, a user might not have know what these icons meant. Now if a user
  hovers over these icons, they get a description of what they mean, for
  example: "This is a bugfix update" or "This update is in the critial path"
  (`#1362 <https://github.com/fedora-infra/bodhi/issues/1362>`_).
* Update pages with lots of updates look cleaner
  (`#1351 <https://github.com/fedora-infra/bodhi/issues/1351>`_).
* Update page titles are shorter now for large updates
  (`#957 <https://github.com/fedora-infra/bodhi/issues/957>`_).
* Add support for alternate architectures to the MasherThread.wait_for_sync()
  (`#1343 <https://github.com/fedora-infra/bodhi/issues/1343>`_).
* Update lists now also include type icons next to the updates
  (`5983d99c <https://github.com/fedora-infra/bodhi/commit/5983d99c>`_).
* Testing updates use a consistent label color now
  (`62330644 <https://github.com/fedora-infra/bodhi/commit/62330644>`_).
* openQA results are now displayed in the web ui
  (`450dbafe <https://github.com/fedora-infra/bodhi/commit/450dbafe>`_).
* Bodhi cookies now expire. There is a new ``authtkt.timeout`` setting that sets Bodhi's session
  lifetime, defaulting to 1 day.


Bugs
^^^^

* Comments that don't carry karma don't count as a user's karma vote
  (`#829 <https://github.com/fedora-infra/bodhi/issues/829>`_).
* The web UI now uses the update alias instead of the title so editors of large updates can click
  the edit button (`#1161 <https://github.com/fedora-infra/bodhi/issues/1161>`_).
* Initialize the bugtracker in ``main()`` instead of on import so that docs can be built without
  installing Bodhi (`#1359 <https://github.com/fedora-infra/bodhi/pull/1359>`_).
* Make the release graph easier to read when there are many datapoints
  (`#1172 <https://github.com/fedora-infra/bodhi/issues/1172>`_).
* Optimize the JavaScript that loads automated test results from ResultsDB
  (`#983 <https://github.com/fedora-infra/bodhi/issues/983>`_).
* Bodhi's testing approval comment now respects the karma reset event
  (`#1310 <https://github.com/fedora-infra/bodhi/issues/1310>`_).
* ``pop`` and ``copy`` now lazily load the configuration
  (`#1423 <https://github.com/fedora-infra/bodhi/issues/1423>`_).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* A new automated PEP-257 test has been introduced to enforce docblocks across the codebase.
  Converting the code will take some time, but the code will be expanded to fully support PEP-257
  eventually. A few modules have now been documented.
* Test coverage is now 84%.
* The Vagrant environment now has vim with a simple vim config to make sure spaces are used instead
  of tabs (`#1372 <https://github.com/fedora-infra/bodhi/pull/1372>`_).
* The Package database model has been converted into a single-table inheritance model, which will
  aid in adding multi-type support to Bodhi. A new RpmPackage model has been added.
  (`#1392 <https://github.com/fedora-infra/bodhi/pull/1392>`_).
* The database initialization code is unified
  (`e9a26042 <https://github.com/fedora-infra/bodhi/commit/e9a26042>`_).
* The base model class now has a helpful query property
  (`8167f262 <https://github.com/fedora-infra/bodhi/commit/8167f262>`_).
* .pyc files are now removed when running the tests in the dev environment
  (`9e9adb61 <https://github.com/fedora-infra/bodhi/commit/9e9adb61>`_).
* An unused inherited column has been dropped from the builds table
  (`e8a95b12 <https://github.com/fedora-infra/bodhi/commit/e8a95b12>`_).


Release contributors
^^^^^^^^^^^^^^^^^^^^

The following contributors submitted patches for Bodhi 2.6.0:

* Jeremy Cline
* Ryan Lerch
* Clement Verna
* Caleigh Runge-Hottman
* Bianca Nenciu
* Adam Williamson
* Ankit Raj Ojha
* Jason Taylor
* Randy Barlow


2.5.0
-----

Bodhi 2.5.0 is a feature and bugfix release.


Features
^^^^^^^^

* The web interface now uses the Fedora Bootstrap theme. The layout of the
  update page has also been revamped to display the information about an update
  in a clearer manner.
  (`#1313 <https://github.com/fedora-infra/bodhi/issues/1313>`_).
* The ``bodhi`` CLI now has a ``--url`` flag that can be used to switch which Bodhi server it
  communicates with. The ``BODHI_URL`` environment can also be used to configure this flag.
* The documentation has been reorganized.
* The Python bindings are now documented.
* Bodhi will now announce that karma has been reset to 0 when builds are added or removed from
  updates (`6d6de4bc <https://github.com/fedora-infra/bodhi/commit/6d6de4bc>`_).
* Bodhi will now announce that autokarma has been disabled when an update received negative karma
  (`d3ccc579 <https://github.com/fedora-infra/bodhi/commit/d3ccc579>`_).
* The docs theme is now Alabaster
  (`57a80f42 <https://github.com/fedora-infra/bodhi/commit/57a80f42>`_).
* The Bodhi documentation now has a description of Bodhi on the landing page
  (`#1322 <https://github.com/fedora-infra/bodhi/issues/1322>`_).
* The REST API is now documented
  (`#1323 <https://github.com/fedora-infra/bodhi/issues/1323>`_).
* The client Python bindings can now accept a ``base_url`` that doesn't end in a slash
  (`1087939b <https://github.com/fedora-infra/bodhi/commit/1087939b>`_).


Bugs
^^^^
* The position of the Add Comment button is now the bottom right.
  (`#902 <https://github.com/fedora-infra/bodhi/issues/902>`_).
* An unusuable ``--request`` flag has been removed from a CLI command
  (`#1187 <https://github.com/fedora-infra/bodhi/issues/1187>`_).
* The cursor is now a pointer when hovering over Releases button
  (`#1296 <https://github.com/fedora-infra/bodhi/issues/1296>`_).
* The number of days to stable is now correctly calculated on updates
  (`#1305 <https://github.com/fedora-infra/bodhi/issues/1305>`_).
* Fix a query regular expression so that Fedora update ids work
  (`d5bec3fa <https://github.com/fedora-infra/bodhi/commit/d5bec3fa>`_).
* Karma thresholds can now be set when autopush is disabled
  (`#1033 <https://github.com/fedora-infra/bodhi/issues/1033>`_).


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^

* The Vagrant development environment automatically configures the BODHI_URL environment
  variable so that the client talks to the local server instead of production or staging.
* Test coverage is up another percentage to 82%.
* Bodhi is now PEP-8 compliant.
* The development environment now displays all Python warnings once.


Release contributors
^^^^^^^^^^^^^^^^^^^^

The following developers contributed to Bodhi 2.5.0:

* Ryan Lerch
* Trishna Guha
* Jeremy Cline
* Ankit Raj Ojha
* Ariel O. Barria
* Randy Barlow


2.4.0
-----

Bodhi 2.4.0 is a feature and bugfix release.


Features
^^^^^^^^
* The web interface now displays whether an update has autopush enabled
  (`#999 <https://github.com/fedora-infra/bodhi/issues/999>`_).
* Autopush is now disabled on any update that receives authenticated negative karma
  (`#1191 <https://github.com/fedora-infra/bodhi/issues/1191>`_).
* Bodhi now links to Koji builds via TLS instead of plaintext
  (`#1246 <https://github.com/fedora-infra/bodhi/issues/1246>`_).
* Some usage examples have been added to the ``bodhi`` man page.
* Bodhi's server package has a new script called ``bodhi-clean-old-mashes`` that can recursively
  delete any folders with names that end in a dash followed by a string that can be interpreted as a
  float, sparing the newest 10 by lexigraphical sorting. This should help release engineers keep the
  Koji mashing folder clean.
* There is now a ``bodhi.client.bindings`` module provided by the Bodhi client package. It contains
  Python bindings to Bodhi's REST API.
* The ``bodhi`` CLI now prints autokarma and thresholds when displaying updates.
* ``bodhi-push`` now has a ``--version`` flag.
* There are now man pages for ``bodhi-push`` and ``initialize_bodhi_db``.


Bugs
^^^^
* Users' e-mail addresses will now be updated when they log in to Bodhi
  (`#902 <https://github.com/fedora-infra/bodhi/issues/902>`_).
* The masher now tests for ``repomd.xml`` instead of the directory that contains it
  (`#908 <https://github.com/fedora-infra/bodhi/issues/908>`_).
* Users can now only upvote an update once
  (`#1018 <https://github.com/fedora-infra/bodhi/issues/1018>`_).
* Only comment on non-autokarma updates when they meet testing requirements
  (`#1009 <https://github.com/fedora-infra/bodhi/issues/1009>`_).
* Autokarma can no longer be set to NULL
  (`#1048 <https://github.com/fedora-infra/bodhi/issues/1048>`_).
* Users can now be more fickle than ever about karma
  (`#1064 <https://github.com/fedora-infra/bodhi/issues/1064>`_).
* Critical path updates can now be free of past negative karma ghosts
  (`#1065 <https://github.com/fedora-infra/bodhi/issues/1065>`_).
* Bodhi now comments on non-autokarma updates after enough time has passed
  (`#1094 <https://github.com/fedora-infra/bodhi/issues/1094>`_).
* ``bodhi-push`` now does not crash when users abort a push
  (`#1107 <https://github.com/fedora-infra/bodhi/issues/1107>`_).
* ``bodhi-push`` now does not print updates when resuming a push
  (`#1113 <https://github.com/fedora-infra/bodhi/issues/1113>`_).
* Bodhi now says "Log in" and "Log out" instead of "Login" and "Logout"
  (`#1146 <https://github.com/fedora-infra/bodhi/issues/1146>`_).
* Bodhi now configures the Koji client to retry, which should help make the masher more reliable
  (`#1201 <https://github.com/fedora-infra/bodhi/issues/1201>`_).
* Bodhi is now compatible with Pillow-4.0.0
  (`#1262 <https://github.com/fedora-infra/bodhi/issues/1262>`_).
* The bodhi cli no longer prints update JSON when setting the request
  (`#1408195 <https://bugzilla.redhat.com/show_bug.cgi?id=1408195>`_).
* Bodhi's signed handler now skips builds that were not assigned to a release.
* The comps file is now cloned into an explicit path during mashing.
* The buildsystem is now locked during login.


Development improvements
^^^^^^^^^^^^^^^^^^^^^^^^
* A great deal of tests were written for Bodhi. Test coverage is now up to 81% and is enforced by
  the test suite.
* Bodhi's server code is now PEP-8 compliant.
* The docs now contain contribution guidelines.
* The build system will now fail with a useful Exception if used without being set up.
* The Vagrantfile is a good bit fancier, with hostname, dnf caching, unsafe but performant disk I/O,
  and more.
* The docs now include a database schema image.
* Bodhi is now run by systemd in the Vagrant guest.
* The Vagrant environment now has several helpful shell aliases and a helpful MOTD to advertise
  them to developers.
* The development environment now uses Fedora 25 by default.
* The test suite is less chatty, as several unicode warnings have been fixed.


Dependency change
^^^^^^^^^^^^^^^^^
* Bodhi server now depends on click for ``bodhi-push``.


Release contributors
^^^^^^^^^^^^^^^^^^^^

The following contributors submitted patches for Bodhi 2.4.0:

* Trishna Guha
* Patrick Uiterwijk
* Jeremy Cline
* Till Mass
* Josef Sukdol
* Clement Verna
* andreas
* Ankit Raj Ojha
* Randy Barlow
