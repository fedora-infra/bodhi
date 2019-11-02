# Copyright © 2011-2019 Red Hat, Inc. and others.
#
# This file is part of Bodhi.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""Bodhi's update models."""

from collections import defaultdict
from datetime import datetime
from textwrap import wrap
import hashlib
import json
import os
import time
import uuid

from sqlalchemy import (and_, Boolean, Column, DateTime, ForeignKey,
                        Integer, or_, Table, Unicode, UnicodeText)
from sqlalchemy.orm import relationship, backref, validates
from sqlalchemy.orm.base import NEVER_SET
from sqlalchemy.orm.exc import NoResultFound
import requests.exceptions
import rpm

from bodhi.messages.schemas import errata as errata_schemas, update as update_schemas
from bodhi.server import buildsys, log, mail, notifications, util
from bodhi.server.config import config
from bodhi.server.exceptions import BodhiException, LockedUpdateException
from bodhi.server.models import (
    metadata, Base, UpdateType, UpdateRequest, UpdateSeverity, UpdateSuggestion,
    UpdateStatus, TestGatingStatus, PackageManager, ReleaseState, Comment, BugKarma,
    TestCaseKarma, Build, Package, Release)
from bodhi.server.tasks import handle_update
from bodhi.server.util import get_critpath_components, tokenize

##
#  Association tables
##

update_bug_table = Table(
    'update_bug_table', metadata,
    Column('update_id', Integer, ForeignKey('updates.id')),
    Column('bug_id', Integer, ForeignKey('bugs.id')))


class Update(Base):
    """
    This model represents an update.

    The update contains not just one package, but a collection of packages. Each
    package can be referenced only once in one Update. Packages are referenced
    through their Build objects using field `builds` below.

    Attributes:
        autokarma (bool): A boolean that indicates whether or not the update will
            be automatically pushed when the stable_karma threshold is reached.
        autotime (bool): A boolean that indicates whether or not the update will
            be automatically pushed when the time threshold is reached.
        stable_karma (int): A positive integer that indicates the amount of "good"
            karma the update must receive before being automatically marked as stable.
        stable_days (int): A positive integer that indicates the number of days an update
            needs to spend in testing before being automatically marked as stable.
        unstable_karma (int): A positive integer that indicates the amount of "bad"
            karma the update must receive before being automatically marked as unstable.
        requirements (str): A list of taskotron tests that must pass for this
            update to be considered stable.
        require_bugs (bool): Indicates whether or not positive feedback needs to be
            provided for the associated bugs before the update can be considered
            stable.
        require_testcases (bool): Indicates whether or not the update requires that
            positive feedback be given on all associated wiki test cases before the
            update can pass to stable. If the update has no associated wiki test cases,
            this option has no effect.
        display_name (str): Allows the user to customize the name of the update.
        notes (str): Notes about the update. This is a human-readable field that
            describes what the update is for (e.g. the bugs it fixes).
        type (EnumSymbol): The type of the update (e.g. enhancement, bugfix, etc). It
            must be one of the values defined in :class:`UpdateType`.
        status (EnumSymbol): The current status of the update. Possible values include
            'pending' to indicate it is not yet in a repository, 'testing' to indicate it
            is in the testing repository, etc. It must be one of the values defined in
            :class:`UpdateStatus`.
        request (EnumSymbol): The requested status of the update. This must be one of the
            values defined in :class:`UpdateRequest` or ``None``.
        severity (EnumSymbol): The update's severity. This must be one of the values defined
            in :class:`UpdateSeverity`.
        suggest (EnumSymbol): Suggested action a user should take after applying the update.
            This must be one of the values defined in :class:`UpdateSuggestion`.
        locked (bool): Indicates whether or not the update is locked and un-editable.
            This is usually set by the composer because the update is going through a state
            transition.
        pushed (bool): Indicates whether or not the update has been pushed to its requested
            repository.
        critpath (bool): Indicates whether or not the update is for a "critical path"
            :class:`Package`. Critical path packages are packages that are required for
            basic functionality. For example, the kernel :class:`RpmPackage` is a critical
            path package.
        close_bugs (bool): Indicates whether the Bugzilla bugs that this update is related
            to should be closed automatically when the update is pushed to stable.
        date_submitted (DateTime): The date that the update was created.
        date_modified (DateTime): The date the update was last modified or ``None``.
        date_approved (DateTime): The date the update was approved or ``None``.
        date_pushed (DateTime): The date the update was pushed or ``None``.
        date_testing (DateTime): The date the update was placed into the testing repository
            or ``None``.
        date_stable (DateTime): The date the update was placed into the stable repository or
            ``None``.
        alias (str): The update alias (e.g. FEDORA-EPEL-2009-12345).
        release_id (int): A foreign key to the releases ``id``.
        release (Release): The ``Release`` object this update relates to via the ``release_id``.
        comments (sqlalchemy.orm.collections.InstrumentedList): A list of the :class:`Comment`
            objects for this update.
        builds (sqlalchemy.orm.collections.InstrumentedList): A list of :class:`Build` objects
            contained in this update.
        bugs (sqlalchemy.orm.collections.InstrumentedList): A list of :class:`Bug` objects
            associated with this update.
        user_id (int): A foreign key to the :class:`User` that created this update.
        test_gating_status (EnumSymbol): The test gating status of the update. This must be one
            of the values defined in :class:`TestGatingStatus` or ``None``. None indicates that
            Greenwave integration was not enabled when the update was created.
        compose (Compose): The :class:`Compose` that this update is currently being composed in. The
            update is locked if this is defined.
        from_tag (str): The koji tag from which the list of builds was
            originally populated (if any).
    """

    __tablename__ = 'updates'
    __exclude_columns__ = ('id', 'user_id', 'release_id')
    __include_extras__ = ('meets_testing_requirements', 'url', 'title', 'version_hash')
    __get_by__ = ('alias',)

    autokarma = Column(Boolean, default=True, nullable=False)
    autotime = Column(Boolean, default=True, nullable=False)
    stable_karma = Column(Integer, nullable=False)
    stable_days = Column(Integer, nullable=False, default=0)
    unstable_karma = Column(Integer, nullable=False)
    requirements = Column(UnicodeText)
    require_bugs = Column(Boolean, default=False)
    require_testcases = Column(Boolean, default=False)

    display_name = Column(UnicodeText, nullable=False, default='')
    notes = Column(UnicodeText, nullable=False)  # Mandatory notes

    # Enumerated types
    type = Column(UpdateType.db_type(), nullable=False)
    status = Column(UpdateStatus.db_type(),
                    default=UpdateStatus.pending,
                    nullable=False, index=True)
    request = Column(UpdateRequest.db_type(), index=True)
    severity = Column(UpdateSeverity.db_type(), default=UpdateSeverity.unspecified)
    suggest = Column(UpdateSuggestion.db_type(), default=UpdateSuggestion.unspecified)

    # Flags
    locked = Column(Boolean, default=False)
    pushed = Column(Boolean, default=False)
    critpath = Column(Boolean, default=False)

    # Bug settings
    close_bugs = Column(Boolean, default=True)

    # Timestamps
    date_submitted = Column(DateTime, default=datetime.utcnow, index=True)
    date_modified = Column(DateTime)
    date_approved = Column(DateTime)
    date_pushed = Column(DateTime)
    date_testing = Column(DateTime)
    date_stable = Column(DateTime)

    # eg: FEDORA-EPEL-2009-12345
    alias = Column(Unicode(64), unique=True, nullable=False)

    # One-to-one relationships
    release_id = Column(Integer, ForeignKey('releases.id'), nullable=False)
    release = relationship('Release', lazy='joined')

    # One-to-many relationships
    comments = relationship('Comment', backref=backref('update', lazy='joined'), lazy='joined',
                            order_by='Comment.timestamp')
    builds = relationship('Build', backref=backref('update', lazy='joined'), lazy='joined',
                          order_by='Build.nvr')
    # If the update is locked and a Compose exists for the same release and request, this will be
    # set to that Compose.
    compose = relationship(
        'Compose',
        primaryjoin=("and_(Update.release_id==Compose.release_id, Update.request==Compose.request, "
                     "Update.locked==True)"),
        foreign_keys=(release_id, request),
        backref=backref('updates', passive_deletes=True))

    # Many-to-many relationships
    bugs = relationship('Bug', secondary=update_bug_table, backref='updates')

    user_id = Column(Integer, ForeignKey('users.id'))

    # Greenwave
    test_gating_status = Column(TestGatingStatus.db_type(), default=None, nullable=True)

    # Koji tag, if any, from which the list of builds was populated initially.
    from_tag = Column(UnicodeText, nullable=True)

    def __init__(self, *args, **kwargs):
        """
        Initialize the Update.

        We use this as a way to inject an alias into the Update, since it is a required field and
        we don't want callers to have to generate the alias themselves.
        """
        # Let's give this Update an alias so the DB doesn't become displeased with us.
        if 'release' not in kwargs:
            raise ValueError('You must specify a Release when creating an Update.')
        prefix = kwargs['release'].id_prefix
        year = time.localtime()[0]
        id = hashlib.sha1(str(uuid.uuid4()).encode('utf-8')).hexdigest()[:10]
        alias = '%s-%s-%s' % (prefix, year, id)
        self.alias = alias
        self.release_id = kwargs['release'].id

        super(Update, self).__init__(*args, **kwargs)

        log.debug('Set alias for %s to %s' % (self.get_title(), alias))

        if self.status == UpdateStatus.testing:
            self._ready_for_testing(self, self.status, None, None)

    @property
    def version_hash(self):
        """
        Return a SHA1 hash of the Builds NVRs.

        Returns:
            str: a SHA1 hash of the builds NVRs.
        """
        nvrs = [x.nvr for x in self.builds]
        builds = " ".join(sorted(nvrs))
        return hashlib.sha1(str(builds).encode('utf-8')).hexdigest()

    @property
    def side_tag_locked(self):
        """
        Return the lock state of the side tag.

        Returns:
            bool: True if sidetag is locked, False otherwise.
        """
        return self.status == UpdateStatus.side_tag_active and self.request is not None

    # WARNING: consumers/composer.py assumes that this validation is performed!
    @validates('builds')
    def validate_builds(self, key, build):
        """
        Validate builds being appended to ensure they are all the same type.

        Args:
            key (str): The field's key, which is un-used in this validator.
            build (Build): The build object which was appended to the list
                of builds.

        Raises:
            ValueError: If the build being appended is not the same type as the
                existing builds.
        """
        if not all([isinstance(b, type(build)) for b in self.builds]):
            raise ValueError('An update must contain builds of the same type.')
        return build

    @validates('release')
    def validate_release(self, key, release):
        """
        Make sure the release is the same content type as this update.

        Args:
            key (str): The field's key, which is un-used in this validator.
            release (Release): The release object which is being associated with this update.
        Raises:
            ValueError: If the release being associated is not the same content type as the
                update.
        """
        if release and self.content_type is not None:
            u = Update.query.filter(Update.release_id == release.id, Update.id != self.id).first()
            if u and u.content_type and u.content_type != self.content_type:
                raise ValueError('A release must contain updates of the same type.')
        return release

    @property
    def date_locked(self):
        """
        Return the time that this update became locked.

        Returns:
            datetime.datetime or None: The time this update became locked, or None if it is not
                locked.
        """
        if self.locked and self.compose is not None:
            return self.compose.date_created

    @property
    def mandatory_days_in_testing(self):
        """
        Calculate and return how many days an update should be in testing before becoming stable.

        :return: The number of mandatory days in testing.
        :rtype:  int
        """
        if self.critpath:
            return config.get('critpath.stable_after_days_without_negative_karma')

        days = self.release.mandatory_days_in_testing
        return days if days else 0

    @property
    def karma(self):
        """
        Calculate and return the karma for the Update.

        :return: The Update's current karma.
        :rtype:  int
        """
        positive_karma, negative_karma = self._composite_karma
        return positive_karma + negative_karma

    @property
    def _composite_karma(self):
        """
        Calculate and return a 2-tuple of the positive and negative karma.

        Sums the positive karma comments, and then sums the negative karma comments. The total karma
        is simply the sum of the two elements of this 2-tuple.

        Returns:
            tuple: A 2-tuple of (positive_karma, negative_karma).
        """
        positive_karma = 0
        negative_karma = 0
        users_counted = set()
        for comment in self.comments_since_karma_reset:
            if comment.karma and comment.user.name not in users_counted:
                # Make sure we only count the last comment this user made
                users_counted.add(comment.user.name)
                if comment.karma > 0:
                    positive_karma += comment.karma
                else:
                    negative_karma += comment.karma

        return positive_karma, negative_karma

    @property
    def comments_since_karma_reset(self):
        """
        Generate the comments since the most recent karma reset event.

        Karma is reset when :class:`Builds <Build>` are added or removed from an update.

        Returns:
            list: class:`Comments <Comment>` since the karma reset.
        """
        # We want to traverse the comments in reverse order so we only consider
        # the most recent comments from any given user and only the comments
        # since the most recent karma reset event.
        comments_since_karma_reset = []

        for comment in reversed(self.comments):
            if comment.user.name == 'bodhi' and \
                    ('New build' in comment.text or 'Removed build' in comment.text):
                # We only want to consider comments since the most recent karma
                # reset, which happens whenever a build is added or removed
                # from an Update. Since we are traversing the comments in
                # reverse order, once we find one of these comments we can
                # simply exit this loop.
                break
            comments_since_karma_reset.append(comment)

        return comments_since_karma_reset

    @staticmethod
    def contains_critpath_component(builds, release_name):
        """
        Determine if there is a critpath component in the builds passed in.

        Args:
            builds (list): :class:`Builds <Build>` to be considered.
            release_name (str): The name of the release, such as "f25".
        Returns:
            bool: ``True`` if the update contains a critical path package, ``False`` otherwise.
        Raises:
            RuntimeError: If the PDC did not give us a 200 code.
        """
        relname = release_name.lower()
        components = defaultdict(list)
        # Get the mess down to a dict of ptype -> [pname]
        for build in builds:
            ptype = build.package.type.value
            pname = build.package.name
            components[ptype].append(pname)

        for ptype in components:
            if get_critpath_components(relname, ptype, frozenset(components[ptype])):
                return True

        return False

    @property
    def greenwave_subject(self):
        """
        Form and return the proper Greenwave API subject field for this Update.

        Returns:
            list: A list of dictionaries that are appropriate to be passed to the Greenwave API
                subject field for a decision about this Update.
        """
        # See discussion on https://pagure.io/greenwave/issue/34 for why we use these subjects.
        subject = [{'item': build.nvr, 'type': 'koji_build'} for build in self.builds]
        subject.append({'item': self.alias, 'type': 'bodhi_update'})
        return subject

    def greenwave_request_batches(self, verbose):
        """
        Form and return the proper Greenwave API requests data for this Update.

        Returns:
            list: A list of dictionaries that are appropriate to be passed to the Greenwave API
                for a decision about this Update.
        """
        batch_size = self.greenwave_subject_batch_size
        count = 0
        subjects = self.greenwave_subject
        data = []
        while count < len(subjects):
            data.append({
                'product_version': self.product_version,
                'decision_context': self._greenwave_decision_context,
                'subject': subjects[count:count + batch_size],
                'verbose': verbose,
            })
            count += batch_size
        return data

    @property
    def greenwave_request_batches_json(self):
        """
        Form and return the proper Greenwave API requests data for this Update as JSON.

        Returns:
            str: A JSON list of objects that are appropriate to be passed to the Greenwave
                API for a decision about this Update.
        """
        return json.dumps(self.greenwave_request_batches(verbose=True))

    @property
    def greenwave_subject_batch_size(self):
        """Maximum number of subjects in single Greenwave request."""
        return config.get('greenwave_batch_size', 8)

    @property
    def _greenwave_api_url(self):
        if not config.get('greenwave_api_url'):
            raise BodhiException('No greenwave_api_url specified')

        return '{}/decision'.format(config.get('greenwave_api_url'))

    @property
    def _greenwave_decision_context(self):
        # We retrieve updates going to testing (status=pending) and updates
        # (status=testing) going to stable.
        # If the update is pending, we want to know if it can go to testing
        if self.request == UpdateRequest.testing and self.status == UpdateStatus.pending:
            return 'bodhi_update_push_testing'
        # Update is already in testing, let's ask if it can go to stable
        return 'bodhi_update_push_stable'

    def get_test_gating_info(self):
        """
        Query Greenwave about this update and return the information retrieved.

        Returns:
            dict: The response from Greenwave for this update.
        Raises:
            BodhiException: When the ``greenwave_api_url`` is undefined in configuration.
            RuntimeError: If Greenwave did not give us a 200 code.
        """
        data = {
            'product_version': self.product_version,
            'decision_context': self._greenwave_decision_context,
            'subject': self.greenwave_subject,
            'verbose': True,
        }
        return util.greenwave_api_post(self._greenwave_api_url, data)

    def _get_test_gating_status(self):
        """
        Query Greenwave about this update and return the information retrieved.

        Returns:
            TestGatingStatus:
                - TestGatingStatus.ignored if no tests are required
                - TestGatingStatus.failed if policies are not satisfied
                - TestGatingStatus.passed if policies are satisfied, and there
                  are required tests

        Raises:
            BodhiException: When the ``greenwave_api_url`` is undefined in configuration.
            RuntimeError: If Greenwave did not give us a 200 code.
        """
        # If an unrestricted policy is applied and no tests are required
        # on this update, let's set the test gating as ignored in Bodhi.
        status = TestGatingStatus.ignored
        for data in self.greenwave_request_batches(verbose=False):
            response = util.greenwave_api_post(self._greenwave_api_url, data)
            if not response['policies_satisfied']:
                return TestGatingStatus.failed

            if status != TestGatingStatus.ignored or response['summary'] != 'no tests are required':
                status = TestGatingStatus.passed

        return status

    @property
    def _unsatisfied_requirements(self):
        unsatisfied_requirements = []
        for data in self.greenwave_request_batches(verbose=False):
            response = util.greenwave_api_post(self._greenwave_api_url, data)
            unsatisfied_requirements.extend(response['unsatisfied_requirements'])

        return unsatisfied_requirements

    @property
    def install_command(self) -> str:
        """
        Return the appropriate command for installing the Update.

        There are three conditions under which the empty string is returned:
            * If the update is not in a stable or testing repository.
            * If the release has not specified a package manager.
            * If the release has not specified a testing repository.

        Returns:
            The dnf command to install the Update, or the empty string.
        """
        if self.status != UpdateStatus.stable and self.status != UpdateStatus.testing:
            return ''

        if self.release.package_manager == PackageManager.unspecified \
                or self.release.testing_repository is None:
            return ''

        command = 'sudo {} {}{} --advisory={}{}'.format(
            self.release.package_manager.value,
            'install' if self.type == UpdateType.newpackage else 'upgrade',
            (' --enablerepo=' + self.release.testing_repository)
            if self.status == UpdateStatus.testing else '',
            self.alias,
            r' \*' if self.type == UpdateType.newpackage else '')
        return command

    def update_test_gating_status(self):
        """Query Greenwave about this update and set the test_gating_status as appropriate."""
        try:
            self.test_gating_status = self._get_test_gating_status()
        except (requests.exceptions.Timeout, RuntimeError) as e:
            log.error(str(e))
            # Greenwave frequently returns 500 response codes. When this happens, we do not want
            # to block updates from proceeding, so we will consider this condition as having the
            # policy satisfied. We will use the Exception as the summary so we can mark the status
            # as ignored for the record.
            self.test_gating_status = TestGatingStatus.greenwave_failed

    @classmethod
    def new(cls, request, data):
        """
        Create a new update.

        Args:
            request (pyramid.request.Request): The current web request.
            data (dict): A key-value mapping of the new update's attributes.
        Returns:
            tuple: A 2-tuple of the edited update and a list of dictionaries that describe caveats.
        Raises:
            RuntimeError: If the PDC did not give us a 200 code.
        """
        from bodhi.server.models import Bug, User

        db = request.db
        user = User.get(request.user.name)
        data['user'] = user
        caveats = []
        data['critpath'] = cls.contains_critpath_component(
            data['builds'], data['release'].name)

        # Create the Bug entities, but don't talk to rhbz yet.  We do that
        # offline in the UpdatesHandler task worker now.
        bugs = []
        if data['bugs']:
            for bug_num in data['bugs']:
                bug = db.query(Bug).filter_by(bug_id=bug_num).first()
                if not bug:
                    bug = Bug(bug_id=bug_num)
                    db.add(bug)
                    db.flush()
                bugs.append(bug)
        data['bugs'] = bugs

        # If no requirements are provided, then gather some defaults from the
        # packages of the associated builds.
        # See https://github.com/fedora-infra/bodhi/issues/101
        if not data['requirements']:
            data['requirements'] = " ".join(list(set(sum([
                list(tokenize(pkg.requirements)) for pkg in [
                    build.package for build in data['builds']
                ] if pkg.requirements], []))))

        del(data['edited'])

        req = data.pop("request", UpdateRequest.testing)

        # Create the update
        log.debug("Creating new Update(**data) object.")
        release = data.pop('release', None)
        up = Update(**data, release=release)

        # We want to make sure that the value of stable_days
        # will not be lower than the mandatory_days_in_testing.
        if up.mandatory_days_in_testing > up.stable_days:
            up.stable_days = up.mandatory_days_in_testing
            caveats.append({
                'name': 'stable days',
                'description': "The number of stable days required was set to the mandatory "
                               f"release value of {up.mandatory_days_in_testing} days"
            })

        if not data.get("from_tag"):
            log.debug("Setting request for new update.")
            up.set_request(db, req, request.user.name)

        log.debug("Adding new update to the db.")
        db.add(up)
        log.debug("Triggering db flush for new update.")
        db.flush()

        if config.get('test_gating.required'):
            log.debug(
                'Test gating required is enforced, marking the update as waiting on test gating')
            up.test_gating_status = TestGatingStatus.waiting

        log.debug("Done with Update.new(...)")
        return up, caveats

    @classmethod
    def edit(cls, request, data):
        """
        Edit the update.

        Args:
            request (pyramid.request.Request): The current web request.
            data (dict): A key-value mapping of what should be altered in this update.
        Returns:
            tuple: A 2-tuple of the edited update and a list of dictionaries that describe caveats.
        Raises:
            LockedUpdateException: If the update is locked.
            RuntimeError: If the PDC did not give us a 200 code.
        """
        db = request.db
        buildinfo = request.buildinfo
        koji = request.koji
        up = db.query(Update).filter_by(alias=data['edited']).first()
        del(data['edited'])

        caveats = []
        edited_builds = [build.nvr for build in up.builds]

        # stable_days can be set by the user. We want to make sure that the value
        # will not be lower than the mandatory_days_in_testing.
        if up.mandatory_days_in_testing > data.get('stable_days', up.stable_days):
            data['stable_days'] = up.mandatory_days_in_testing
            caveats.append({
                'name': 'stable days',
                'description': "The number of stable days required was raised to the mandatory "
                               f"release value of {up.mandatory_days_in_testing} days"
            })

        # Determine which builds have been added
        new_builds = []
        for build in data['builds']:
            if build not in edited_builds:
                if up.locked:
                    raise LockedUpdateException("Can't add builds to a "
                                                "locked update")

                new_builds.append(build)
                Package.get_or_create(buildinfo[build])
                b = db.query(Build).filter_by(nvr=build).first()

                up.builds.append(b)

        # Determine which builds have been removed
        removed_builds = []
        for build in edited_builds:
            if build not in data['builds']:
                if up.locked:
                    raise LockedUpdateException("Can't remove builds from a "
                                                "locked update")

                removed_builds.append(build)
                b = None
                for b in up.builds:
                    if b.nvr == build:
                        break

                b.unpush(koji=request.koji)
                up.builds.remove(b)

                # Expire any associated buildroot override
                if b.override:
                    log.debug(f"Expiring BRO for {b.nvr} because the build is unpushed.")
                    b.override.expire()
                else:
                    # Only delete the Build entity if it isn't associated with
                    # an override
                    db.delete(b)

        data['critpath'] = cls.contains_critpath_component(
            up.builds, up.release.name)

        del(data['builds'])

        # Comment on the update with details of added/removed builds
        # .. enumerate the builds in markdown format so they're pretty.
        comment = '%s edited this update.' % request.user.name
        if new_builds:
            comment += '\n\nNew build(s):\n'
            for new_build in new_builds:
                comment += "\n- %s" % new_build
        if removed_builds:
            comment += '\n\nRemoved build(s):\n'
            for removed_build in removed_builds:
                comment += "\n- %s" % removed_build
        if new_builds or removed_builds:
            comment += '\n\nKarma has been reset.'
        up.comment(db, comment, karma=0, author='bodhi')
        caveats.append({'name': 'builds', 'description': comment})

        # Updates with new or removed builds always go back to testing
        if new_builds or removed_builds:
            data['request'] = UpdateRequest.testing

            # Remove all koji tags and change the status back to pending
            if up.status is not UpdateStatus.pending:
                up.unpush(db)
                caveats.append({
                    'name': 'status',
                    'description': 'Builds changed.  Your update is being '
                    'sent back to testing.',
                })

            # Add the pending_signing_tag to all new builds
            for build in new_builds:
                if up.from_tag:
                    # this is a sidetag based update. use the sidetag pending signing tag
                    side_tag_pending_signing = up.release.get_pending_signing_side_tag(up.from_tag)
                    koji.tagBuild(side_tag_pending_signing, build)
                elif up.release.pending_signing_tag:
                    # Add the release's pending_signing_tag to all new builds
                    koji.tagBuild(up.release.pending_signing_tag, build)
                else:
                    # EL6 doesn't have these, and that's okay...
                    # We still warn in case the config gets messed up.
                    log.warning('%s has no pending_signing_tag' % up.release.name)

        # And, updates with new or removed builds always get their karma reset.
        # https://github.com/fedora-infra/bodhi/issues/511
        if new_builds or removed_builds:
            data['karma_critpath'] = 0

        new_bugs = up.update_bugs(data['bugs'], db)
        del(data['bugs'])

        req = data.pop("request", None)
        if req is not None and not data.get("from_tag"):
            up.set_request(db, req, request.user.name)

        for key, value in data.items():
            setattr(up, key, value)

        up.date_modified = datetime.utcnow()

        handle_update.delay(
            api_version=1, action='edit',
            update=up.__json__(request=request),
            agent=request.user.name,
            new_bugs=new_bugs
        )
        notifications.publish(update_schemas.UpdateEditV1.from_dict(
            message={'update': up, 'agent': request.user.name, 'new_bugs': new_bugs}))

        return up, caveats

    @property
    def signed(self):
        """
        Return whether the update is considered signed or not.

        This will return ``True`` if all :class:`Builds <Build>` associated with this update are
        signed, or if the associated :class:`Release` does not have a ``pending_signing_tag``
        defined. Otherwise, it will return ``False``.

        If the update is created ``from_tag`` always check if every build is signed.

        Returns:
            bool: ``True`` if the update is signed, ``False`` otherwise.
        """
        if not self.release.pending_signing_tag and not self.from_tag:
            return True
        return all([build.signed for build in self.builds])

    @property
    def content_type(self):
        """
        Return the ContentType associated with this update.

        If the update has no :class:`Builds <Build>`, this evaluates to ``None``.

        Returns:
            ContentType or None: The content type of this update or ``None``.
        """
        if self.builds:
            return self.builds[0].type

    @property
    def test_gating_passed(self) -> bool:
        """
        Returns a boolean representing if this update has passed the test gating.

        Returns:
            True if the Update's test_gating_status property is None,
            greenwave_failed, ignored, or passed. Otherwise it returns False.
        """
        if self.test_gating_status in (
                None, TestGatingStatus.greenwave_failed, TestGatingStatus.ignored,
                TestGatingStatus.passed):
            return True
        return False

    def obsolete_older_updates(self, db):
        """Obsolete any older pending/testing updates.

        If a build is associated with multiple updates, make sure that
        all updates are safe to obsolete, or else just skip it.

        Args:
            db (sqlalchemy.orm.session.Session): A database session.
        Returns:
            list: A list of dictionaries that describe caveats.
        """
        caveats = []
        for build in self.builds:
            for oldBuild in db.query(Build).join(Update).filter(
                and_(Build.nvr != build.nvr,
                     Build.package == build.package,
                     Update.locked == False,
                     Update.release == self.release,
                     or_(Update.request == UpdateRequest.testing,
                         Update.request == None),
                     or_(Update.status == UpdateStatus.testing,
                         Update.status == UpdateStatus.pending))
            ).all():
                obsoletable = False
                nvr = build.get_n_v_r()
                if rpm.labelCompare(oldBuild.get_n_v_r(), nvr) < 0:
                    log.debug("%s is newer than %s" % (nvr, oldBuild.nvr))
                    obsoletable = True

                # Ensure that all of the packages in the old update are
                # present in the new one.
                pkgs = [b.package.name for b in self.builds]
                for _build in oldBuild.update.builds:
                    if _build.package.name not in pkgs:
                        obsoletable = False
                        break

                # Warn if you're stomping on another user but don't necessarily
                # obsolete them
                if len(oldBuild.update.builds) != len(self.builds):
                    if oldBuild.update.user.name != self.user.name:
                        caveats.append({
                            'name': 'update',
                            'description': 'Please be aware that there '
                            'is another update in flight owned by %s, '
                            'containing %s. Are you coordinating with '
                            'them?' % (
                                oldBuild.update.user.name,
                                oldBuild.nvr,
                            )
                        })

                # Warn about attempt to obsolete security update by update with
                # other type and set type of new update to security.
                if oldBuild.update.type == UpdateType.security and \
                        self.type is not UpdateType.security:
                    caveats.append({
                        'name': 'update',
                        'description': 'Adjusting type of this update to security,'
                        'since it obsoletes another security update'
                    })
                    self.type = UpdateType.security

                if obsoletable:
                    log.info('%s is obsoletable' % oldBuild.nvr)

                    # Have the newer update inherit the older updates bugs
                    oldbugs = [bug.bug_id for bug in oldBuild.update.bugs]
                    bugs = [bug.bug_id for bug in self.bugs]
                    self.update_bugs(bugs + oldbugs, db)

                    # Also inherit the older updates notes as well and
                    # add a markdown separator between the new and old ones.
                    self.notes += '\n\n----\n\n' + oldBuild.update.notes
                    oldBuild.update.obsolete(db, newer=build)
                    template = ('This update has obsoleted %s, and has '
                                'inherited its bugs and notes.')
                    link = "[%s](%s)" % (oldBuild.nvr,
                                         oldBuild.update.abs_url())
                    self.comment(db, template % link, author='bodhi')
                    caveats.append({
                        'name': 'update',
                        'description': template % oldBuild.nvr,
                    })

        return caveats

    def get_tags(self):
        """
        Return all koji tags for all builds on this update.

        Returns:
            list: strings of the koji tags used in this update.
        """
        return list(set(sum([b.get_tags() for b in self.builds], [])))

    @property
    def title(self) -> str:
        """
        Return the Update's title.

        This is just an alias for get_title with default parameters.
        """
        return self.get_title()

    def get_title(self, delim=' ', limit=None, after_limit='…',
                  beautify=False, nvr=False, amp=False):
        """
        Return a title for the update based on the :class:`Builds <Build>` it is associated with.

        Args:
            delim (str): The delimiter used to separate the builds. Defaults to ' '.
            limit (int or None): If provided, limit the number of builds included to the given
                number. If ``None`` (the default), no limit is used.
            after_limit (str): If a limit is set, use this string after the limit is reached.
                Defaults to '…'.
            beautify (bool): If provided, the returned string will be human
                readable, i.e. 3 or more builds will take the form "package1,
                package2 and XXX more".
            nvr (bool): If specified, the title will include name, version and
                release information in package labels.
            amp (bool): If specified, it will replace the word 'and' with an
                ampersand, '&'.
        Returns:
            str: A title for this update.
        """
        if beautify:
            if self.display_name:
                return self.display_name

            def build_label(build):
                return build.nvr if nvr else build.package.name

            if len(self.builds) > 2:
                title = ", ".join([build_label(build) for build in self.builds[:2]])

                if amp:
                    title += ", & "
                else:
                    title += ", and "
                title += str(len(self.builds) - 2)
                title += " more"

                return title
            else:
                return " and ".join([build_label(build) for build in self.builds])
        else:
            all_nvrs = [x.nvr for x in self.builds]
            nvrs = all_nvrs[:limit]
            builds = delim.join(sorted(nvrs)) + \
                (after_limit if limit and len(all_nvrs) > limit else "")
            return builds

    def get_bugstring(self, show_titles=False):
        """
        Return a space-delimited string of bug numbers for this update.

        Args:
            show_titles (bool): If True, include the bug titles in the output. If False, include
                only bug ids.
        Returns:
            str: A space separated list of bugs associated with this update.
        """
        val = ''
        if show_titles:
            i = 0
            for bug in self.bugs:
                bugstr = '%s%s - %s\n' % (
                    i and ' ' * 11 + ': ' or '', bug.bug_id, bug.title)
                val += '\n'.join(wrap(
                    bugstr, width=67,
                    subsequent_indent=' ' * 11 + ': ')) + '\n'
                i += 1
            val = val[:-1]
        else:
            val = ' '.join([str(bug.bug_id) for bug in self.bugs])
        return val

    def get_bug_karma(self, bug):
        """
        Return the karma for this update for the given bug.

        Args:
            bug (Bug): The bug we want the karma about.
        Returns:
            tuple: A 2-tuple of integers. The first represents negative karma, the second represents
            positive karma.
        """
        good, bad, seen = 0, 0, set()
        for comment in self.comments_since_karma_reset:
            if comment.user.name in seen:
                continue
            seen.add(comment.user.name)
            for feedback in comment.bug_feedback:
                if feedback.bug == bug:
                    if feedback.karma > 0:
                        good += 1
                    elif feedback.karma < 0:
                        bad += 1
        return bad * -1, good

    def get_testcase_karma(self, testcase):
        """
        Return the karma for this update for the given TestCase.

        Args:
            testcase (TestCase): The TestCase we want the karma about.
        Returns:
            tuple: A 2-tuple of integers. The first represents negative karma, the second represents
            positive karma.
        """
        good, bad, seen = 0, 0, set()
        for comment in self.comments_since_karma_reset:
            if comment.user.name in seen:
                continue
            seen.add(comment.user.name)
            for feedback in comment.unique_testcase_feedback:
                if feedback.testcase == testcase:
                    if feedback.karma > 0:
                        good += 1
                    elif feedback.karma < 0:
                        bad += 1
        return bad * -1, good

    def set_request(self, db, action, username):
        """
        Set the update's request to the given action.

        Args:
            db (sqlalchemy.orm.session.Session): A database session.
            action (UpdateRequest or str): The desired request. May be expressed as an
                UpdateRequest instance, or as a string describing the desired request.
            username (str): The username of the user making the request.
        Raises:
            BodhiException: Two circumstances can raise this ``Exception``:

                * If the user tries to push a critical path update directly from pending to stable.
                * If the update doesn't meet testing requirements.

            LockedUpdateException: If the update is locked.
        """
        log.debug('Attempting to set request %s' % action)
        notes = []
        if isinstance(action, str):
            action = UpdateRequest.from_string(action)
        if self.status and action.description == self.status.description:
            log.info("%s already %s" % (self.alias, action.description))
            return
        if action is self.request:
            log.debug("%s has already been submitted to %s" % (self.alias,
                                                               self.request.description))
            return

        if self.locked:
            raise LockedUpdateException("Can't change the request on a "
                                        "locked update")

        if action is UpdateRequest.unpush:
            self.unpush(db)
            self.comment(db, u'This update has been unpushed.', author=username)
            notifications.publish(update_schemas.UpdateRequestUnpushV1.from_dict(dict(
                update=self, agent=username)))
            log.debug("%s has been unpushed." % self.alias)
            return
        elif action is UpdateRequest.obsolete:
            self.obsolete(db)
            log.debug("%s has been obsoleted." % self.alias)
            notifications.publish(update_schemas.UpdateRequestObsoleteV1.from_dict(dict(
                update=self, agent=username)))
            return

        # If status is pending going to testing request and action is revoke,
        # set the status to unpushed
        elif self.status is UpdateStatus.pending and self.request is UpdateRequest.testing \
                and action is UpdateRequest.revoke:
            self.status = UpdateStatus.unpushed
            self.revoke()
            log.debug("%s has been revoked." % self.alias)
            notifications.publish(update_schemas.UpdateRequestRevokeV1.from_dict(dict(
                update=self, agent=username)))
            return

        # If status is testing going to stable request and action is revoke,
        # keep the status at testing
        elif self.request == UpdateRequest.stable and \
                self.status is UpdateStatus.testing and action is UpdateRequest.revoke:
            self.revoke()
            log.debug("%s has been revoked." % self.alias)
            notifications.publish(update_schemas.UpdateRequestRevokeV1.from_dict(dict(
                update=self, agent=username)))
            return

        elif action is UpdateRequest.revoke:
            self.revoke()
            log.debug("%s has been revoked." % self.alias)
            notifications.publish(update_schemas.UpdateRequestRevokeV1.from_dict(dict(
                update=self, agent=username)))
            return

        # Disable pushing critical path updates for pending releases directly to stable
        if action == UpdateRequest.stable and self.critpath:
            if config.get('critpath.num_admin_approvals') is not None:
                if not self.critpath_approved:
                    stern_note = (
                        'This critical path update has not yet been approved for pushing to the '
                        'stable repository.  It must first reach a karma of %s, consisting of %s '
                        'positive karma from proventesters, along with %d additional karma from '
                        'the community. Or, it must spend %s days in testing without any negative '
                        'feedback')
                    additional_karma = config.get('critpath.min_karma') \
                        - config.get('critpath.num_admin_approvals')
                    stern_note = stern_note % (
                        config.get('critpath.min_karma'),
                        config.get('critpath.num_admin_approvals'),
                        additional_karma,
                        config.get('critpath.stable_after_days_without_negative_karma'))
                    if config.get('test_gating.required'):
                        stern_note += ' Additionally, it must pass automated tests.'
                    notes.append(stern_note)

                    if self.status is UpdateStatus.testing:
                        self.request = None
                        raise BodhiException('. '.join(notes))
                    else:
                        log.info('Forcing critical path update into testing')
                        action = UpdateRequest.testing

        # Ensure this update meets the minimum testing requirements
        flash_notes = ''
        if action == UpdateRequest.stable and not self.critpath:
            # Check if we've met the karma requirements
            if self.karma >= self.stable_karma or self.critpath_approved:
                log.debug('%s meets stable karma requirements' % self.alias)
            else:
                # If we haven't met the stable karma requirements, check if it
                # has met the mandatory time-in-testing requirements
                if self.mandatory_days_in_testing:
                    if not self.has_stable_comment and \
                       not self.meets_testing_requirements:
                        if self.release.id_prefix == "FEDORA-EPEL":
                            flash_notes = config.get('not_yet_tested_epel_msg')
                        else:
                            flash_notes = config.get('not_yet_tested_msg')
                        if self.status is UpdateStatus.testing:
                            self.request = None
                            raise BodhiException(flash_notes)
                        elif self.request is UpdateRequest.testing:
                            raise BodhiException(flash_notes)
                        else:
                            action = UpdateRequest.testing

        # Add the appropriate 'pending' koji tag to this update, so tools like
        # AutoQA can compose repositories of them for testing.
        if action is UpdateRequest.testing:
            self.add_tag(self.release.pending_signing_tag)
        elif action is UpdateRequest.stable:
            self.add_tag(self.release.pending_stable_tag)

        # If an obsolete/unpushed build is being re-submitted, return
        # it to the pending state, and make sure it's tagged as a candidate
        if self.status in (UpdateStatus.obsolete, UpdateStatus.unpushed):
            self.status = UpdateStatus.pending
            if self.release.candidate_tag not in self.get_tags():
                self.add_tag(self.release.candidate_tag)

        self.request = action

        notes = notes and '. '.join(notes) + '.' or ''
        flash_notes = flash_notes and '. %s' % flash_notes
        log.debug(
            "%s has been submitted for %s. %s%s" % (
                self.alias, action.description, notes, flash_notes))

        comment_text = 'This update has been submitted for %s by %s. %s' % (
            action.description, username, notes)
        # Add information about push to stable delay to comment when release is frozen.
        if self.release.state == ReleaseState.frozen and action == UpdateRequest.stable:
            comment_text += (
                "\n\nThere is an ongoing freeze; this will be "
                "pushed to stable after the freeze is over. "
            )
        self.comment(db, comment_text, author=u'bodhi')

        if action == UpdateRequest.testing:
            handle_update.delay(
                api_version=1, action="testing",
                update=self.__json__(),
                agent=username
            )
        action_message_map = {
            UpdateRequest.revoke: update_schemas.UpdateRequestRevokeV1,
            UpdateRequest.stable: update_schemas.UpdateRequestStableV1,
            UpdateRequest.testing: update_schemas.UpdateRequestTestingV1,
            UpdateRequest.unpush: update_schemas.UpdateRequestUnpushV1,
            UpdateRequest.obsolete: update_schemas.UpdateRequestObsoleteV1}
        notifications.publish(action_message_map[action].from_dict(
            dict(update=self, agent=username)))

    def waive_test_results(self, username, comment=None, tests=None):
        """
        Attempt to waive test results for this update.

        Args:
            username (str): The name of the user who is waiving the test results.
            comment (str): A comment from the user describing their decision.
            tests (list of str): A list of testcases to be waived. Defaults to ``None``
                If left as ``None``, all ``unsatisfied_requirements`` returned by greenwave
                will be waived, otherwise only the testcase found in both list will be waived.
        Raises:
            LockedUpdateException: If the Update is locked.
            BodhiException: If test gating is not enabled in this Bodhi instance,
                            or if the tests have passed.
            RuntimeError: Either WaiverDB or Greenwave did not give us a 200 code.
        """
        log.debug('Attempting to waive test results for this update %s' % self.alias)

        if self.locked:
            raise LockedUpdateException("Can't waive test results on a "
                                        "locked update")

        if not config.get('test_gating.required'):
            raise BodhiException('Test gating is not enabled')

        if self.test_gating_passed:
            raise BodhiException("Can't waive test results on an update that passes test gating")

        # Ensure we can always iterate over tests
        tests = tests or []

        for requirement in self._unsatisfied_requirements:

            if tests and requirement['testcase'] not in tests:
                continue

            data = {
                'subject': requirement['item'],
                'testcase': requirement['testcase'],
                'product_version': self.product_version,
                'waived': True,
                'username': username,
                'comment': comment
            }
            log.debug('Waiving test results: %s' % data)
            util.waiverdb_api_post(
                '{}/waivers/'.format(config.get('waiverdb_api_url')), data)

        self.test_gating_status = TestGatingStatus.waiting

    def add_tag(self, tag):
        """
        Add the given koji tag to all :class:`Builds <Build>` in this update.

        Args:
            tag (str): The tag to be added to the builds.
        """
        log.debug('Adding tag %s to %s', tag, self.get_title())
        if not tag:
            log.warning("Not adding builds of %s to empty tag", self.title)
            return []  # An empty iterator in place of koji multicall

        koji = buildsys.get_session()
        koji.multicall = True
        for build in self.builds:
            koji.tagBuild(tag, build.nvr, force=True)
        return koji.multiCall()

    def remove_tag(self, tag, koji=None):
        """
        Remove the given koji tag from all builds in this update.

        Args:
            tag (str): The tag to remove from the :class:`Builds <Build>` in this update.
            koji (koji.ClientSession or None): A koji client to use to perform the action. If None
                (the default), this method will use :func:`buildsys.get_session` to get one and
                multicall will be used.
        Returns:
            list or None: If a koji client was provided, ``None`` is returned. Else, a list of tasks
                from ``koji.multiCall()`` are returned.
        """
        log.debug('Removing tag %s from %s', tag, self.get_title())
        if not tag:
            log.warning("Not removing builds of %s from empty tag", self.get_title())
            return []  # An empty iterator in place of koji multicall

        return_multicall = not koji
        if not koji:
            koji = buildsys.get_session()
            koji.multicall = True
        for build in self.builds:
            koji.untagBuild(tag, build.nvr, force=True)
        if return_multicall:
            return koji.multiCall()

    def find_conflicting_builds(self) -> list:
        """
        Find if there are any builds conflicting with the stable tag in the update.

        Returns a list of conflicting builds, empty is none found.
        """
        conflicting_builds = []
        for build in self.builds:
            if not build.is_latest():
                conflicting_builds.append(build.nvr)

        return conflicting_builds

    def modify_bugs(self):
        """
        Comment on and close this update's bugs as necessary.

        This typically gets called by the Composer at the end.
        """
        if self.status is UpdateStatus.testing:
            for bug in self.bugs:
                log.debug('Adding testing comment to bugs for %s', self.alias)
                bug.testing(self)
        elif self.status is UpdateStatus.stable:
            if not self.close_bugs:
                for bug in self.bugs:
                    log.debug('Adding stable comment to bugs for %s', self.alias)
                    bug.add_comment(self)
            else:
                if self.type is UpdateType.security:
                    # Only close the tracking bugs
                    # https://github.com/fedora-infra/bodhi/issues/368#issuecomment-135155215
                    for bug in self.bugs:
                        if not bug.parent:
                            log.debug("Closing tracker bug %d" % bug.bug_id)
                            bug.close_bug(self)
                else:
                    for bug in self.bugs:
                        bug.close_bug(self)

    def status_comment(self, db):
        """
        Add a comment to this update about a change in status.

        Args:
            db (sqlalchemy.orm.session.Session): A database session.
        """
        if self.status is UpdateStatus.stable:
            self.comment(db, 'This update has been pushed to stable.',
                         author='bodhi')
        elif self.status is UpdateStatus.testing:
            self.comment(db, 'This update has been pushed to testing.',
                         author='bodhi')
        elif self.status is UpdateStatus.obsolete:
            self.comment(db, 'This update has been obsoleted.', author='bodhi')

    def send_update_notice(self):
        """Send e-mail notices about this update."""
        log.debug("Sending update notice for %s", self.alias)
        mailinglist = None
        sender = config.get('bodhi_email')
        if not sender:
            log.error(("bodhi_email not defined in configuration!  Unable "
                      "to send update notice"))
            return

        # eg: fedora_epel
        release_name = self.release.id_prefix.lower().replace('-', '_')
        if self.status is UpdateStatus.stable:
            mailinglist = config.get('%s_announce_list' % release_name)
        elif self.status is UpdateStatus.testing:
            mailinglist = config.get('%s_test_announce_list' % release_name)

        if mailinglist:
            for subject, body in mail.get_template(self, self.release.mail_template):
                mail.send_mail(sender, mailinglist, subject, body)
                notifications.publish(errata_schemas.ErrataPublishV1.from_dict(
                    dict(subject=subject, body=body, update=self)))
        else:
            log.error("Cannot find mailing list address for update notice")
            log.error("release_name = %r", release_name)

    def get_url(self):
        """
        Return the relative URL to this update.

        Returns:
            str: A URL.
        """
        path = ['updates']
        path.append(self.alias)
        return os.path.join(*path)

    def abs_url(self, request=None):
        """
        Return the absolute URL to this update.

        Args:
            request (pyramid.request.Request or None): The current web request. Unused.
        """
        base = config['base_address']
        return os.path.join(base, self.get_url())

    url = abs_url

    def __str__(self):
        """
        Return a string representation of this update.

        Returns:
            str: A string representation of the update.
        """
        val = "%s\n%s\n%s\n" % ('=' * 80, '\n'.join(wrap(
            self.alias, width=80, initial_indent=' ' * 5,
            subsequent_indent=' ' * 5)), '=' * 80)
        val += """    Release: %s
     Status: %s
       Type: %s
   Severity: %s
      Karma: %d""" % (self.release.long_name, self.status.description,
                      self.type.description, self.severity, self.karma)
        if self.critpath:
            val += "\n   Critpath: %s" % self.critpath
        if self.request is not None:
            val += "\n    Request: %s" % self.request.description
        if len(self.bugs):
            bugs = self.get_bugstring(show_titles=True)
            val += "\n       Bugs: %s" % bugs
        if self.notes:
            notes = wrap(
                self.notes, width=67, subsequent_indent=' ' * 11 + ': ')
            val += "\n      Notes: %s" % '\n'.join(notes)
        username = None
        if self.user:
            username = self.user.name
        val += """
  Submitter: %s
  Submitted: %s\n""" % (username, self.date_submitted)
        if self.comments_since_karma_reset:
            val += "   Comments: "
            comments = []
            for comment in self.comments_since_karma_reset:
                comments.append("%s%s - %s (karma %s)" % (' ' * 13,
                                comment.user.name, comment.timestamp,
                                comment.karma))
                if comment.text:
                    text = wrap(comment.text, initial_indent=' ' * 13,
                                subsequent_indent=' ' * 13, width=67)
                    comments.append('\n'.join(text))
            val += '\n'.join(comments).lstrip() + '\n'
        val += "\n  %s\n" % self.abs_url()
        return val

    def update_bugs(self, bug_ids, session):
        """
        Make the update's bugs consistent with the given list of bug ids.

        Create any new bugs, and remove any missing ones. Destroy removed bugs that are no longer
        referenced anymore. If any associated bug is found to be a security bug, alter the update to
        be a security update.

        Args:
            bug_ids (list): A list of strings of bug ids to associate with this update.
            session (sqlalchemy.orm.session.Session): A database session.
        Returns:
            list: :class:`Bugs <Bug>` that are newly associated with the update.
        """
        from bodhi.server.models import Bug

        to_remove = [bug for bug in self.bugs if bug.bug_id not in bug_ids]

        for bug in to_remove:
            self.bugs.remove(bug)
            if len(bug.updates) == 0:
                # Don't delete the Bug instance if there is any associated BugKarma
                if not session.query(BugKarma).filter_by(bug_id=bug.bug_id).count():
                    log.debug("Destroying stray Bugzilla #%d" % bug.bug_id)
                    session.delete(bug)
        session.flush()

        new = []
        for bug_id in bug_ids:
            bug = Bug.get(int(bug_id))
            if not bug:
                bug = Bug(bug_id=int(bug_id))
                session.add(bug)
                session.flush()
            if bug not in self.bugs:
                self.bugs.append(bug)
                new.append(bug.bug_id)
            if bug.security and self.type != UpdateType.security:
                self.type = UpdateType.security

        session.flush()
        return new

    def obsolete_if_unstable(self, db):
        """
        Obsolete the update if it reached the negative karma threshold while pending.

        Args:
            db (sqlalchemy.orm.session.Session): A database session.
        """
        if self.autokarma and self.status is UpdateStatus.pending \
                and self.request is UpdateRequest.testing\
                and self.karma <= self.unstable_karma:
            log.info("%s has reached unstable karma thresholds", self.alias)
            self.obsolete(db)
            log.debug("%s has been obsoleted.", self.alias)
        return

    def comment(self, session, text, karma=0, author=None, karma_critpath=0,
                bug_feedback=None, testcase_feedback=None, check_karma=True,
                email_notification=True):
        """Add a comment to this update.

        If the karma reaches the 'stable_karma' value, then request that this update be marked
        as stable. If it reaches the 'unstable_karma', it is unpushed.
        """
        from bodhi.server.models import User

        if not author:
            raise ValueError('You must provide a comment author')

        # Listify these
        bug_feedback = bug_feedback or []
        testcase_feedback = testcase_feedback or []

        got_feedback = False
        for feedback_dict in (bug_feedback + testcase_feedback):
            if feedback_dict['karma'] != 0:
                got_feedback = True
                break

        if (not text and not karma and not karma_critpath and not got_feedback):
            raise ValueError('You must provide either some text or feedback')

        caveats = []

        if self.user.name == author:
            if karma != 0:
                karma = 0
                notice = 'You may not give karma to your own updates.'
                caveats.append({'name': 'karma', 'description': notice})

        comment = Comment(text=text, karma=karma, karma_critpath=karma_critpath)
        session.add(comment)

        try:
            user = session.query(User).filter_by(name=author).one()
        except NoResultFound:
            user = User(name=author)
            session.add(user)

        user.comments.append(comment)
        self.comments.append(comment)
        session.flush()

        if karma != 0:
            # Determine whether this user has already left karma, and if so what the most recent
            # karma value they left was. We should examine all but the most recent comment, since
            # that is the comment we just added.
            previous_karma = None
            for c in reversed(self.comments[:-1]):
                if c.user.name == author and c.karma:
                    previous_karma = c.karma
                    break
            if previous_karma and karma != previous_karma:
                caveats.append({
                    'name': 'karma',
                    'description': 'Your karma standing was reversed.',
                })
            else:
                log.debug('Ignoring duplicate %d karma from %s on %s', karma, author, self.alias)

            log.info("Updated %s karma to %d", self.alias, self.karma)

            if check_karma and author not in config.get('system_users'):
                try:
                    self.check_karma_thresholds(session, 'bodhi')
                except LockedUpdateException:
                    pass
                except BodhiException as e:
                    # This gets thrown if the karma is pushed over the
                    # threshold, but it is a critpath update that is not
                    # critpath_approved. ... among other cases.
                    log.exception('Problem checking the karma threshold.')
                    caveats.append({
                        'name': 'karma', 'description': str(e),
                    })

            # Obsolete pending update if it reaches unstable karma threshold
            self.obsolete_if_unstable(session)

        session.flush()

        for feedback_dict in bug_feedback:
            feedback = BugKarma(**feedback_dict)
            session.add(feedback)
            comment.bug_feedback.append(feedback)

        for feedback_dict in testcase_feedback:
            feedback = TestCaseKarma(**feedback_dict)
            session.add(feedback)
            comment.testcase_feedback.append(feedback)

        session.flush()

        # Publish to Fedora Messaging
        if author not in config.get('system_users'):
            notifications.publish(update_schemas.UpdateCommentV1.from_dict(
                {'comment': comment.__json__(), 'agent': author}))

        # Send a notification to everyone that has commented on this update
        people = set()
        for person in self.get_maintainers():
            if person.email:
                people.add(person.email)
            else:
                people.add(person.name)
        for comment in self.comments:
            if comment.user.name in ['anonymous', 'bodhi']:
                continue
            if comment.user.email:
                people.add(comment.user.email)
            else:
                people.add(comment.user.name)
        if email_notification:
            mail.send(people, 'comment', self, sender=None, agent=author)
        return comment, caveats

    def unpush(self, db):
        """
        Move this update back to its dist-fX-updates-candidate tag.

        Args:
            db (sqlalchemy.orm.session.Session): A database session.
        Raises:
            BodhiException: If the update isn't in testing.
        """
        log.debug("Unpushing %s", self.alias)
        koji = buildsys.get_session()

        if self.status is UpdateStatus.unpushed:
            log.debug("%s already unpushed", self.alias)
            return

        if self.status is not UpdateStatus.testing:
            raise BodhiException("Can't unpush a %s update"
                                 % self.status.description)

        self.untag(db)

        for build in self.builds:
            koji.tagBuild(self.release.candidate_tag, build.nvr, force=True)

        self.pushed = False
        self.status = UpdateStatus.unpushed
        self.request = None

    def revoke(self):
        """
        Remove pending request for this update.

        Raises:
            BodhiException: If the update doesn't have a request set, or if it is not in an expected
                status.
        """
        log.debug("Revoking %s", self.alias)

        if not self.request:
            raise BodhiException(
                "Can only revoke an update with an existing request")

        if self.status not in [UpdateStatus.pending, UpdateStatus.testing,
                               UpdateStatus.obsolete, UpdateStatus.unpushed]:
            raise BodhiException(
                "Can only revoke a pending, testing, unpushed, or obsolete "
                "update, not one that is %s" % self.status.description)

        # Remove the 'pending' koji tags from this update so taskotron stops
        # evaluating them.
        if self.request is UpdateRequest.testing:
            self.remove_tag(self.release.pending_signing_tag)
            self.remove_tag(self.release.pending_testing_tag)
        elif self.request is UpdateRequest.stable:
            self.remove_tag(self.release.pending_stable_tag)

        self.request = None

    def untag(self, db):
        """
        Untag all of the :class:`Builds <Build>` in this update.

        Args:
            db (sqlalchemy.orm.session.Session): A database session.
        """
        log.info("Untagging %s", self.alias)
        koji = buildsys.get_session()
        tag_types, tag_rels = Release.get_tags(db)
        for build in self.builds:
            for tag in build.get_tags():
                # Only remove tags that we know about
                if tag in tag_rels:
                    koji.untagBuild(tag, build.nvr, force=True)
                else:
                    log.info("Skipping tag that we don't know about: %s" % tag)
        self.pushed = False

    def obsolete(self, db, newer=None):
        """
        Obsolete this update.

        Even though unpushing/obsoletion is an "instant" action, changes in the repository will not
        propagate until the next compose takes place.

        Args:
            db (sqlalchemy.orm.session.Session): A database session.
            newer (Update or None): If given, the update that has obsoleted this one. Defaults to
                ``None``.
        """
        log.debug("Obsoleting %s", self.alias)
        self.untag(db)
        self.status = UpdateStatus.obsolete
        self.request = None
        if newer:
            self.comment(db, "This update has been obsoleted by [%s](%s)." % (
                newer.nvr, newer.update.abs_url()), author='bodhi')
        else:
            self.comment(db, "This update has been obsoleted.", author='bodhi')

    def get_maintainers(self):
        """
        Return a list of maintainers who have commit access on the packages in this update.

        Returns:
            list: A list of :class:`Users <User>` who have commit access to all of the
                packages that are contained within this update.
        """
        return [self.user]

    @property
    def product_version(self):
        """
        Return a string of the product version that this update's release is associated with.

        The product version is a string, such as "fedora-26", and is used when querying Greenwave
        for test gating decisions.

        Returns:
            str: The product version associated with this Update's Release.
        """
        return self.release.long_name.lower().replace(' ', '-')

    def check_requirements(self, session, settings):
        """
        Check that an update meets its self-prescribed policy to be pushed.

        Args:
            session (sqlalchemy.orm.session.Session): A database session. Unused.
            settings (bodhi.server.config.BodhiConfig): Bodhi's settings.
        Returns:
            tuple: A tuple containing (result, reason) where result is a bool
                and reason is a str.
        """
        if config.get('test_gating.required') and not self.test_gating_passed:
            return (False, "Required tests did not pass on this update")

        requirements = tokenize(self.requirements or '')
        requirements = list(requirements)

        if not requirements:
            return True, "No checks required."

        try:
            # https://github.com/fedora-infra/bodhi/issues/362
            since = self.last_modified.isoformat().rsplit('.', 1)[0]
        except Exception as e:
            log.exception("Failed to determine last_modified from %r : %r",
                          self.last_modified, str(e))
            return False, "Failed to determine last_modified: %r" % str(e)

        try:
            # query results for this update
            query = dict(type='bodhi_update', item=self.alias, since=since,
                         testcases=','.join(requirements))
            results = list(util.taskotron_results(settings, **query))

            # query results for each build
            # retrieve timestamp for each build so that queries can be optimized
            koji = buildsys.get_session()
            koji.multicall = True
            for build in self.builds:
                koji.getBuild(build.nvr)
            buildinfos = koji.multiCall()

            for index, build in enumerate(self.builds):
                multicall_response = buildinfos[index]
                if not isinstance(multicall_response, list) \
                        or not isinstance(multicall_response[0], dict):
                    msg = ("Error retrieving data from Koji for %r: %r" %
                           (build.nvr, multicall_response))
                    log.error(msg)
                    raise TypeError(msg)

                buildinfo = multicall_response[0]
                ts = datetime.utcfromtimestamp(buildinfo['completion_ts']).isoformat()

                query = dict(type='koji_build', item=build.nvr, since=ts,
                             testcases=','.join(requirements))
                build_results = list(util.taskotron_results(settings, **query))
                results.extend(build_results)

        except Exception as e:
            log.exception("Failed retrieving requirements results: %r", str(e))
            return False, "Failed retrieving requirements results: %r" % str(e)

        for testcase in requirements:
            relevant = [result for result in results
                        if result['testcase']['name'] == testcase]

            if not relevant:
                return False, 'No result found for required testcase %s' % testcase

            by_arch = defaultdict(list)
            for result in relevant:
                arch = result['data'].get('arch', ['noarch'])[0]
                by_arch[arch].append(result)

            for arch, result in by_arch.items():
                latest = relevant[0]  # resultsdb results are ordered chronologically
                if latest['outcome'] not in ['PASSED', 'INFO']:
                    return False, "Required task %s returned %s" % (
                        latest['testcase']['name'], latest['outcome'])

        # TODO - check require_bugs and require_testcases also?

        return True, "All checks pass."

    def check_karma_thresholds(self, db, agent):
        """
        Check if we have reached either karma threshold, and adjust state as necessary.

        This method will call :meth:`set_request` if necessary. If the update is locked, it will
        ignore karma thresholds and raise an Exception.

        Args:
            db (sqlalchemy.orm.session.Session): A database session.
            agent (str): The username of the user who has provided karma.
        Raises:
            LockedUpdateException: If the update is locked.
        """
        # Raise Exception if the update is locked
        if self.locked:
            log.debug('%s locked. Ignoring karma thresholds.', self.alias)
            raise LockedUpdateException
        # Return if the status of the update is not in testing or pending
        if self.status not in (UpdateStatus.testing, UpdateStatus.pending):
            return
        # If an update receives negative karma disable autopush
        if (self.autokarma or self.autotime) and self._composite_karma[1] != 0 and self.status is \
                UpdateStatus.testing and self.request is not UpdateRequest.stable:
            log.info("Disabling Auto Push since the update has received negative karma")
            self.autokarma = False
            self.autotime = False
            text = config.get('disable_automatic_push_to_stable')
            self.comment(db, text, author='bodhi')
        elif self.stable_karma and self.karma >= self.stable_karma:
            if self.autokarma:
                log.info("Automatically marking %s as stable", self.alias)
                self.set_request(db, UpdateRequest.stable, agent)
                self.date_pushed = None
                notifications.publish(update_schemas.UpdateKarmaThresholdV1.from_dict(
                    dict(update=self, status='stable')))
            else:
                # Add the stable approval message now
                log.info((
                    "%s update has reached the stable karma threshold and can be pushed to "
                    "stable now if the maintainer wishes"), self.alias)
        elif self.unstable_karma and self.karma <= self.unstable_karma:
            if self.status is UpdateStatus.pending and not self.autokarma:
                pass
            else:
                log.info("Automatically unpushing %s", self.alias)
                self.obsolete(db)
                notifications.publish(update_schemas.UpdateKarmaThresholdV1.from_dict(
                    dict(update=self, status='unstable')))

    @property
    def builds_json(self):
        """
        Return a JSON representation of this update's associated builds.

        Returns:
            str: A JSON list of the :class:`Builds <Build>` associated with this update.
        """
        return json.dumps([build.nvr for build in self.builds])

    @property
    def requirements_json(self):
        """
        Return a JSON representation of this update's requirements.

        Returns:
            str: A JSON representation of this update's requirements.
        """
        return json.dumps(list(tokenize(self.requirements or '')))

    @property
    def last_modified(self):
        """
        Return the last time this update was edited or created.

        This gets used specifically by taskotron/resultsdb queries so we only
        query for test runs that occur *after* the last time this update
        (in its current form) was in play.

        Returns:
            datetime.datetime: The most recent time of modification or creation.
        Raises:
            ValueError: If the update has no timestamps set, which should not be possible.
        """
        # Prune out None values that have not been set
        possibilities = [self.date_submitted, self.date_modified]
        possibilities = [p for p in possibilities if p]

        if not possibilities:  # Should be un-possible.
            raise ValueError("Update has no timestamps set: %r" % self)

        possibilities.sort()  # Sort smallest to largest (oldest to newest)
        return possibilities[-1]  # Return the last one

    @property
    def critpath_approved(self):
        """
        Return whether or not this critpath update has been approved.

        Returns:
            bool: True if this update meets critpath testing requirements, False otherwise.
        """
        # https://fedorahosted.org/bodhi/ticket/642
        if self.meets_testing_requirements:
            return True
        min_karma = self.release.critpath_min_karma
        if self.release.setting_status:
            num_admin_approvals = config.get(
                f'{self.release.setting_prefix}.{self.release.setting_status}'
                '.critpath.num_admin_approvals')
            if num_admin_approvals is not None and min_karma:
                return self.num_admin_approvals >= int(num_admin_approvals) and \
                    self.karma >= min_karma
        return self.num_admin_approvals >= config.get('critpath.num_admin_approvals') and \
            self.karma >= min_karma

    @property
    def meets_testing_requirements(self):
        """
        Return whether or not this update meets its release's testing requirements.

        If this update's release does not have a mandatory testing requirement, then
        simply return True.

        Returns:
            bool: True if the update meets testing requirements, False otherwise.
        """
        num_days = self.mandatory_days_in_testing

        if config.get('test_gating.required') and not self.test_gating_passed:
            return False

        if self.karma >= self.release.critpath_min_karma:
            return True

        if self.critpath:
            # Ensure there is no negative karma. We're looking at the sum of
            # each users karma for this update, which takes into account
            # changed votes.
            if self._composite_karma[1] < 0:
                return False
            return self.days_in_testing >= num_days

        if not num_days:
            return True

        if self.karma >= self.stable_karma:
            return True

        # Any update that reaches num_days has met the testing requirements.
        return self.days_in_testing >= num_days

    @property
    def has_stable_comment(self):
        """
        Return whether Bodhi has commented on the update that the requirements have been met.

        This is used to determine whether bodhi should add the comment
        about the Update's eligibility to be pushed, as we only want Bodhi
        to add the comment once.

        Returns:
            bool: See description above for what the bool might mean.
        """
        for comment in self.comments_since_karma_reset:
            if comment.user.name == 'bodhi' and \
               comment.text.startswith('This update ') and \
               'can be pushed to stable now if the maintainer wishes' in comment.text:
                return True
        return False

    @property
    def days_to_stable(self):
        """
        Return the number of days until an update can be pushed to stable.

        This method will return the number of days until an update can be pushed to stable, or 0.
        0 is returned if the update meets testing requirements already, if it doesn't have a
        "truthy" date_testing attribute, or if it's been in testing for the release's
        mandatory_days_in_testing or longer.

        Returns:
            int: The number of dates until this update can be pushed to stable, or 0 if it cannot be
                determined.
        """
        if not self.meets_testing_requirements and self.date_testing:
            num_days = (self.mandatory_days_in_testing - self.days_in_testing)
            if num_days > 0:
                return num_days
        return 0

    @property
    def days_in_testing(self):
        """
        Return the number of days that this update has been in testing.

        Returns:
            int: The number of days since this update's date_testing if it is set, else 0.
        """
        if self.date_testing:
            return (datetime.utcnow() - self.date_testing).days
        else:
            return 0

    @property
    def num_admin_approvals(self):
        """
        Return the number of Releng/QA approvals of this update.

        Returns:
            int: The number of admin approvals found in the comments of this update.
        """
        approvals = 0
        for comment in self.comments_since_karma_reset:
            if comment.karma != 1:
                continue
            admin_groups = config.get('admin_groups')
            for group in comment.user.groups:
                if group.name in admin_groups:
                    approvals += 1
                    break
        return approvals

    @property
    def test_cases(self):
        """
        Return a list of all TestCase names associated with all packages in this update.

        Returns:
            list: A list of strings naming the :class:`TestCases <TestCase>` associated with
                this update.
        """
        tests = set()
        for build in self.builds:
            for test in build.package.test_cases:
                tests.add(test.name)
        return sorted(list(tests))

    @property
    def full_test_cases(self):
        """
        Return a list of all TestCases associated with all packages in this update.

        Returns:
            list: A list of :class:`TestCases <TestCase>`.
        """
        tests = set()
        for build in self.builds:
            test_names = set()
            for test in build.package.test_cases:
                if test.name not in test_names:
                    test_names.add(test.name)
                    tests.add(test)
        return sorted(list(tests), key=lambda testcase: testcase.name)

    @property
    def requested_tag(self):
        """
        Return the tag the update has requested.

        Returns:
            str: The Koji tag that corresponds to the update's current request.
        Raises:
            RuntimeError: If a Koji tag is unable to be determined.
        """
        tag = None
        if self.request is UpdateRequest.stable:
            tag = self.release.stable_tag
            # [No Frozen Rawhide] Move stable builds going to a pending
            # release to the Release.dist-tag
            if self.release.state is ReleaseState.pending:
                tag = self.release.dist_tag
        elif self.request == UpdateRequest.testing:
            tag = self.release.testing_tag
        elif self.request is UpdateRequest.obsolete:
            tag = self.release.candidate_tag
        if not tag:
            raise RuntimeError(
                f'Unable to determine requested tag for {self.alias}.')
        return tag

    def __json__(self, request=None):
        """
        Return a JSON representation of this update.

        Args:
            request (pyramid.request.Request or None): The current web request,
                or None. Passed on to :meth:`BodhiBase.__json__`.
        Returns:
            str: A JSON representation of this update.
        """
        result = super(Update, self).__json__(request=request)
        # Duplicate alias as updateid for backwards compat with bodhi1
        result['updateid'] = result['alias']
        # Include the karma total in the results
        result['karma'] = self.karma
        # Also, the Update content_type (derived from the builds content_types)
        result['content_type'] = self.content_type.value if self.content_type else None

        # For https://github.com/fedora-infra/bodhi/issues/270, throw the JSON
        # of the test cases in our output as well but take extra care to
        # short-circuit some of the insane recursion for
        # https://github.com/fedora-infra/bodhi/issues/343
        seen = [Package, TestCaseKarma]
        result['test_cases'] = [
            test._to_json(
                obj=test,
                seen=seen,
                request=request)
            for test in self.full_test_cases
        ]

        return result

    @staticmethod
    def comment_on_test_gating_status_change(target, value, old, initiator):
        """
        Place comment on the update when ``test_gating_status`` changes.

        Only notify the users by email if the new status is in ``failed`` or
        ``greenwave_failed``.

        Args:
            target (InstanceState): The state of the instance that has had a
                change to its test_gating_status attribute.
            value (EnumSymbol): The new value of the test_gating_status.
            old (EnumSymbol): The old value of the test_gating_status
            initiator (sqlalchemy.orm.attributes.Event): The event object that is initiating this
                transition.
        """
        instance = target.object

        if value != old:
            notify = value in [
                TestGatingStatus.greenwave_failed,
                TestGatingStatus.failed,
            ]
            instance.comment(
                target.session,
                f"This update's test gating status has been changed to '{value}'.",
                author="bodhi",
                email_notification=notify,
            )

    def _build_group_test_message(self):
        """
        Build the dictionary sent when an update is ready to be tested.

        This is used in bodhi.server.models.Update._ready_for_testing and in
        bodhi.server.services.updates.trigger_tests which are the two places
        where we send notifications about an update being ready to be tested
        by any CI system.

        Args:
            target (Update): The update that has had a change to its status attribute.
        Returns:
            dict: A dictionary corresponding to the message sent
        """
        contact = {
            "name": "Bodhi",
            "email": "admin@fp.o",
            "team": "Fedora CI",
            "docs": "https://docs.fedoraproject.org/en-US/ci/",
        }
        builds = []
        for build in self.builds:
            builds.append({
                "type": "koji-build",
                "id": build.get_build_id(),
                "task_id": build.get_task_id(),
                "issuer": build.get_owner_name(),
                "component": build.nvr_name,
                "nvr": build.nvr,
                "scratch": False,
            })

        artifact = {
            "type": "koji-build-group",
            "id": f"{self.alias}-{self.version_hash}",
            "repository": self.abs_url(),
            "builds": builds,
            "release": self.release.dist_tag,
        }
        return {
            "contact": contact,
            "artifact": artifact,
            "generated_at": datetime.utcnow().isoformat() + 'Z',
            "version": "0.2.2",
            'agent': 'bodhi',
            're-trigger': False,
        }

    @staticmethod
    def _ready_for_testing(target, value, old, initiator):
        """
        Signal that the update has been moved to testing.

        This happens in the following cases:
        - for stable releases: the update lands in the testing repository
        - for rawhide: all packages in an update have been built by koji

        Args:
            target (Update): The update that has had a change to its status attribute.
            value (EnumSymbol): The new value of Update.status.
            old (EnumSymbol): The old value of the Update.status
            initiator (sqlalchemy.orm.attributes.Event): The event object that is initiating this
                transition.
        """
        if value != UpdateStatus.testing or value == old:
            return
        if old == NEVER_SET:
            # This is the object initialization phase. This instance is not ready, don't create
            # the message now. This method will be called again at the end of __init__
            return

        message = update_schemas.UpdateReadyForTestingV1.from_dict(
            message=target._build_group_test_message()
        )
        notifications.publish(message)
