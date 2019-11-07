# Copyright 2007-2019 Red Hat, Inc. and others.
#
# This file is part of Bodhi.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from datetime import datetime, timedelta
from hashlib import sha256
from os.path import join, exists, basename
from unittest import mock
import glob
import os
import shutil
import tempfile

import createrepo_c

from bodhi.server.buildsys import (setup_buildsystem, teardown_buildsystem,
                                   DevBuildsys)
from bodhi.server.config import config
from bodhi.server.models import Release, Update, UpdateRequest, UpdateStatus
from bodhi.server.metadata import UpdateInfoMetadata
import bodhi.server.metadata as bodhi_metadata
from bodhi.tests.server import base, create_update


class UpdateInfoMetadataTestCase(base.BaseTestCase):
    def setUp(self):
        """
        Initialize our temporary repo.
        """
        super(UpdateInfoMetadataTestCase, self).setUp()
        setup_buildsystem({'buildsystem': 'dev'})
        self.tempdir = tempfile.mkdtemp('bodhi')
        self.tempcompdir = join(self.tempdir, 'f17-updates-testing')
        self.temprepo = join(self.tempcompdir, 'compose', 'Everything', 'i386', 'os')
        base.mkmetadatadir(join(self.temprepo, 'f17-updates-testing', 'i386'), updateinfo=False)
        config['cache_dir'] = os.path.join(self.tempdir, 'cache')
        os.makedirs(config['cache_dir'])

    def tearDown(self):
        """
        Clean up the tempdir.
        """
        super(UpdateInfoMetadataTestCase, self).tearDown()
        teardown_buildsystem()
        shutil.rmtree(self.tempdir)
        config['cache_dir'] = None


class TestAddUpdate(UpdateInfoMetadataTestCase):
    """
    This class contains tests for the UpdateInfoMetadata.add_update() method.
    """

    def test_build_not_in_builds(self):
        """
        Test correct behavior when a build in update.builds isn't found in self.builds() and
        koji.getBuild() is called instead.
        """
        update = self.db.query(Update).one()
        now = datetime(year=2018, month=2, day=8, hour=12, minute=41, second=4)
        update.date_pushed = now
        update.date_modified = now
        md = UpdateInfoMetadata(update.release, update.request, self.db, self.temprepo,
                                close_shelf=False)

        md.add_update(update)

        md.shelf.close()

        self.assertEqual(len(md.uinfo.updates), 1)
        self.assertEqual(md.uinfo.updates[0].title, update.title)
        self.assertEqual(md.uinfo.updates[0].release, update.release.long_name)
        self.assertEqual(md.uinfo.updates[0].status, update.status.value)
        self.assertEqual(md.uinfo.updates[0].updated_date, update.date_modified)
        self.assertEqual(md.uinfo.updates[0].fromstr, config.get('bodhi_email'))
        self.assertEqual(md.uinfo.updates[0].rights, config.get('updateinfo_rights'))
        self.assertEqual(md.uinfo.updates[0].description, update.notes)
        self.assertEqual(md.uinfo.updates[0].id, update.alias)
        self.assertEqual(md.uinfo.updates[0].severity, 'Moderate')
        self.assertEqual(len(md.uinfo.updates[0].references), 1)
        bug = md.uinfo.updates[0].references[0]
        self.assertEqual(bug.href, update.bugs[0].url)
        self.assertEqual(bug.id, '12345')
        self.assertEqual(bug.type, 'bugzilla')
        self.assertEqual(len(md.uinfo.updates[0].collections), 1)
        col = md.uinfo.updates[0].collections[0]
        self.assertEqual(col.name, update.release.long_name)
        self.assertEqual(col.shortname, update.release.name)
        self.assertEqual(len(col.packages), 2)
        pkg = col.packages[0]
        self.assertEqual(pkg.epoch, '0')
        # It's a little goofy, but the DevBuildsys is going to return TurboGears rpms when its
        # listBuildRPMs() method is called, so let's just roll with it.
        self.assertEqual(pkg.name, 'TurboGears')
        self.assertEqual(
            pkg.src,
            ('https://download.fedoraproject.org/pub/fedora/linux/updates/17/SRPMS/T/'
             'TurboGears-1.0.2.2-2.fc17.src.rpm'))
        self.assertEqual(pkg.version, '1.0.2.2')
        self.assertFalse(pkg.reboot_suggested)
        self.assertEqual(pkg.arch, 'src')
        self.assertEqual(pkg.filename, 'TurboGears-1.0.2.2-2.fc17.src.rpm')
        pkg = col.packages[1]
        self.assertEqual(pkg.epoch, '0')
        self.assertEqual(pkg.name, 'TurboGears')
        self.assertEqual(
            pkg.src,
            ('https://download.fedoraproject.org/pub/fedora/linux/updates/17/i386/T/'
             'TurboGears-1.0.2.2-2.fc17.noarch.rpm'))
        self.assertEqual(pkg.version, '1.0.2.2')
        self.assertFalse(pkg.reboot_suggested)
        self.assertEqual(pkg.arch, 'noarch')
        self.assertEqual(pkg.filename, 'TurboGears-1.0.2.2-2.fc17.noarch.rpm')

    def test_date_modified_none(self):
        """The metadata should use utcnow() if an update's date_modified is None."""
        test_start_time = datetime.utcnow()
        # The UpdateRecord's updated_date attribute strips microseconds, so let's force them to 0
        # so our assertions at the end of this test will pass.
        test_start_time = test_start_time - timedelta(microseconds=test_start_time.microsecond)
        update = self.db.query(Update).one()
        update.date_modified = None
        md = UpdateInfoMetadata(update.release, update.request, self.db, self.temprepo,
                                close_shelf=False)

        md.add_update(update)

        md.shelf.close()
        self.assertEqual(len(md.uinfo.updates), 1)
        self.assertTrue(test_start_time <= md.uinfo.updates[0].updated_date <= datetime.utcnow())

    def test_date_pushed_none(self):
        """The metadata should use utcnow() if an update's date_pushed is None."""
        test_start_time = datetime.utcnow()
        # The UpdateRecord's updated_date attribute strips microseconds, so let's force them to 0
        # so our assertions at the end of this test will pass.
        test_start_time = test_start_time - timedelta(microseconds=test_start_time.microsecond)
        update = self.db.query(Update).one()
        update.date_pushed = None
        md = UpdateInfoMetadata(update.release, update.request, self.db, self.temprepo,
                                close_shelf=False)

        md.add_update(update)

        md.shelf.close()
        self.assertEqual(len(md.uinfo.updates), 1)
        self.assertTrue(test_start_time <= md.uinfo.updates[0].issued_date <= datetime.utcnow())

    def test_rpm_with_arch(self):
        """Ensure that an RPM with a non 386 arch gets handled correctly."""
        update = self.db.query(Update).one()
        md = UpdateInfoMetadata(update.release, update.request, self.db, self.temprepo,
                                close_shelf=False)
        # Set the arch to aarch64
        fake_rpms = [{
            'nvr': 'TurboGears-1.0.2.2-2.fc17', 'buildtime': 1178868422, 'arch': 'aarch64',
            'id': 62330, 'size': 761742, 'build_id': 6475, 'name': 'TurboGears', 'epoch': None,
            'version': '1.0.2.2', 'release': '2.fc17', 'buildroot_id': 1883,
            'payloadhash': '6787febe92434a9be2a8f309d0e2014e'}]

        with mock.patch.object(md, 'get_rpms', mock.MagicMock(return_value=fake_rpms)):
            md.add_update(update)

        md.shelf.close()
        col = md.uinfo.updates[0].collections[0]
        self.assertEqual(len(col.packages), 1)
        pkg = col.packages[0]
        self.assertEqual(
            pkg.src,
            ('https://download.fedoraproject.org/pub/fedora/linux/updates/17/aarch64/T/'
             'TurboGears-1.0.2.2-2.fc17.aarch64.rpm'))

    def test_rpm_with_epoch(self):
        """Ensure that an RPM with an Epoch gets handled correctly."""
        update = self.db.query(Update).one()
        md = UpdateInfoMetadata(update.release, update.request, self.db, self.temprepo,
                                close_shelf=False)
        # We'll fake the return of get_rpms so we can inject an epoch of 42.
        fake_rpms = [{
            'nvr': 'TurboGears-1.0.2.2-2.fc17', 'buildtime': 1178868422, 'arch': 'src', 'id': 62330,
            'size': 761742, 'build_id': 6475, 'name': 'TurboGears', 'epoch': 42,
            'version': '1.0.2.2', 'release': '2.fc17', 'buildroot_id': 1883,
            'payloadhash': '6787febe92434a9be2a8f309d0e2014e'}]

        with mock.patch.object(md, 'get_rpms', mock.MagicMock(return_value=fake_rpms)):
            md.add_update(update)

        md.shelf.close()
        col = md.uinfo.updates[0].collections[0]
        self.assertEqual(len(col.packages), 1)
        pkg = col.packages[0]
        self.assertEqual(pkg.epoch, '42')


class TestFetchUpdates(UpdateInfoMetadataTestCase):
    """Test the UpdateInfoMetadata._fetch_updates() method."""

    @mock.patch('bodhi.server.metadata.log.warning')
    def test_build_unassociated(self, warning):
        """A warning should be logged if the Bodhi Build object is not associated with an Update."""
        update = self.db.query(Update).one()
        update.date_pushed = None
        u = create_update(self.db, ['TurboGears-1.0.2.2-4.fc17'])
        u.builds[0].update = None
        self.db.flush()

        # _fetch_updates() is called as part of UpdateInfoMetadata.__init__() so we'll just
        # instantiate one.
        md = UpdateInfoMetadata(update.release, update.request, self.db, self.temprepo,
                                close_shelf=False)

        warning.assert_called_once_with(
            'TurboGears-1.0.2.2-4.fc17 does not have a corresponding update')
        # Since the Build didn't have an Update, no Update should have been added to md.updates.
        self.assertEqual(md.updates, set([]))


class TestUpdateInfoMetadata(UpdateInfoMetadataTestCase):

    def setUp(self):
        super(TestUpdateInfoMetadata, self).setUp()

        self._new_compose_stage_dir = tempfile.mkdtemp()
        self._compose_stage_dir = config['compose_stage_dir']
        self._compose_dir = config['compose_dir']
        config['compose_stage_dir'] = self._new_compose_stage_dir
        config['compose_dir'] = os.path.join(config['compose_stage_dir'], 'compose')
        config['cache_dir'] = os.path.join(config['compose_stage_dir'], 'cache')
        os.makedirs(config['cache_dir'])
        os.makedirs(os.path.join(config['compose_dir'], 'f17-updates-testing'))

        # Initialize our temporary repo
        base.mkmetadatadir(self.temprepo, updateinfo=False)
        base.mkmetadatadir(join(self.tempcompdir, 'compose', 'Everything', 'source', 'tree'),
                           updateinfo=False)
        self.repodata = join(self.temprepo, 'repodata')
        self.assertTrue(exists(join(self.repodata, 'repomd.xml')))

        DevBuildsys.__rpms__ = [{
            'arch': 'src',
            'build_id': 6475,
            'buildroot_id': 1883,
            'buildtime': 1178868422,
            'epoch': None,
            'id': 62330,
            'name': 'bodhi',
            'nvr': 'bodhi-2.0-1.fc17',
            'release': '1.fc17',
            'size': 761742,
            'version': '2.0'
        }]

    def tearDown(self):
        config['compose_stage_dir'] = self._compose_stage_dir
        config['compose_dir'] = self._compose_dir
        config['cache_dir'] = None
        shutil.rmtree(self._new_compose_stage_dir)
        super(TestUpdateInfoMetadata, self).tearDown()

    def _verify_updateinfos(self, repodata):
        updateinfos = glob.glob(join(repodata, "*-updateinfo.xml*"))
        if hasattr(createrepo_c, 'ZCK_COMPRESSION'):
            self.assertEqual(
                len(updateinfos), 2, "We generated %d updateinfo metadata" % len(updateinfos))
        else:
            self.assertEqual(
                len(updateinfos), 1, "We generated %d updateinfo metadata" % len(updateinfos))
        for updateinfo in updateinfos:
            hash = basename(updateinfo).split("-", 1)[0]
            with open(updateinfo, 'rb') as fn:
                hashed = sha256(fn.read()).hexdigest()
            self.assertEqual(hash, hashed, "File: %s\nHash: %s" % (basename(updateinfo), hashed))

        return updateinfos

    def get_notice(self, uinfo, title):
        for record in uinfo.updates:
            if record.title == title:
                return record

    def test___init___uses_bz2_for_epel(self):
        """Assert that the __init__() method sets the comp_type attribute to cr.BZ2 for EPEL."""
        epel_7 = Release(id_prefix="FEDORA-EPEL", stable_tag='epel7')

        md = UpdateInfoMetadata(epel_7, UpdateRequest.stable, self.db, self.tempdir)

        self.assertEqual(md.comp_type, createrepo_c.BZ2)
        self.assertFalse(md.zchunk)

    def test___init___uses_xz_for_fedora(self):
        """Assert that the __init__() method sets the comp_type attribute to cr.XZ for Fedora."""
        fedora = Release.query.one()

        md = UpdateInfoMetadata(fedora, UpdateRequest.stable, self.db, self.tempdir)

        self.assertEqual(md.comp_type, createrepo_c.XZ)
        self.assertTrue(md.zchunk)

    def test_extended_metadata_once(self):
        """Assert that a single call to update the metadata works as expected."""
        self._test_extended_metadata()

    def test_extended_metadata_cache(self):
        """Asserts that when the same update is retrieved twice, the info is unshelved.

        After the first run, we clear the buildsystem.__rpms__ so that there would be no way to
        again retrieve the info from the buildsystem, and it'll have to be returned from the
        cache.
        """
        self._test_extended_metadata()
        shutil.rmtree(self.temprepo)
        base.mkmetadatadir(self.temprepo, updateinfo=False)
        base.mkmetadatadir(join(self.tempcompdir, 'compose', 'Everything', 'source', 'tree'),
                           updateinfo=False)
        DevBuildsys.__rpms__ = []
        self._test_extended_metadata()

    def _test_extended_metadata(self):
        update = self.db.query(Update).one()

        # Pretend it's pushed to testing
        update.status = UpdateStatus.testing
        update.request = None
        update.date_pushed = datetime.utcnow()
        DevBuildsys.__tagged__[update.title] = ['f17-updates-testing']

        # Generate the XML
        md = UpdateInfoMetadata(update.release, update.request, self.db, self.tempcompdir)

        # Insert the updateinfo.xml into the repository
        md.insert_updateinfo(self.tempcompdir)
        updateinfos = self._verify_updateinfos(self.repodata)

        for updateinfo in updateinfos:
            # Read an verify the updateinfo.xml.gz
            uinfo = createrepo_c.UpdateInfo(updateinfo)
            notice = self.get_notice(uinfo, 'mutt-1.5.14-1.fc13')
            self.assertIsNone(notice)

            self.assertEqual(len(uinfo.updates), 1)
            notice = uinfo.updates[0]

            self.assertIsNotNone(notice)
            self.assertEqual(notice.title, update.title)
            self.assertEqual(notice.release, update.release.long_name)
            self.assertEqual(notice.status, update.status.value)
            if update.date_modified:
                self.assertEqual(notice.updated_date, update.date_modified)
            self.assertEqual(notice.fromstr, config.get('bodhi_email'))
            self.assertEqual(notice.rights, config.get('updateinfo_rights'))
            self.assertEqual(notice.description, update.notes)
            self.assertEqual(notice.id, update.alias)
            self.assertEqual(notice.severity, 'Moderate')
            bug = notice.references[0]
            self.assertEqual(bug.href, update.bugs[0].url)
            self.assertEqual(bug.id, '12345')
            self.assertEqual(bug.type, 'bugzilla')

            col = notice.collections[0]
            self.assertEqual(col.name, update.release.long_name)
            self.assertEqual(col.shortname, update.release.name)

            pkg = col.packages[0]
            self.assertEqual(pkg.epoch, '0')
            self.assertEqual(pkg.name, 'TurboGears')
            self.assertEqual(
                pkg.src,
                ('https://download.fedoraproject.org/pub/fedora/linux/updates/testing/17/SRPMS/T/'
                 'TurboGears-1.0.2.2-2.fc17.src.rpm'))
            self.assertEqual(pkg.version, '1.0.2.2')
            self.assertFalse(pkg.reboot_suggested)
            self.assertEqual(pkg.arch, 'src')
            self.assertEqual(pkg.filename, 'TurboGears-1.0.2.2-2.fc17.src.rpm')

    @mock.patch('bodhi.server.metadata.cr')
    def test_zchunk_metadata_coverage_xz_compression(self, mock_cr):
        """
        Let's test that we skip zchunk files, because we don't want to zchunk zchunk files.

        This test makes sure we reach 100% coverage by mocking createrepo.

        cr.ZCK_COMPRESSION is only defined when createrepo_c supports zchunk, but createrepo_c's
        zchunk support is only available in createrepo_c >= 0.12.0, and it is also a build flag,
        so we can't be sure that the createrepo_c we work with has that feature.

        This function is designed to *only* make sure we reach 100% coverage and isn't meant
        to test whether zchunk is working correctly.  _test_extended_metadata will take care
        of testing both the regular and zchunked updateinfo if zchunk is enabled
        """
        mock_cr.ZCK_COMPRESSION = 99
        mock_repomd = mock.MagicMock()
        mock_repomd.xml_dump = mock.MagicMock(return_value="test data")
        mock_cr.Repomd = mock.MagicMock(return_value=mock_repomd)

        bodhi_metadata.insert_in_repo(bodhi_metadata.cr.XZ_COMPRESSION, self.tempcompdir,
                                      'garbage', 'zck', '/dev/null', True)

        mock_cr.Repomd.assert_called_once_with(os.path.join(self.tempcompdir, 'repomd.xml'))
        self.assertEqual(
            mock_cr.RepomdRecord.mock_calls,
            [mock.call('garbage', os.path.join(self.tempcompdir, 'garbage.zck')),
             mock.call().compress_and_fill(mock_cr.SHA256, mock_cr.XZ_COMPRESSION),
             mock.call().compress_and_fill().rename_file(),
             mock.call('garbage_zck', os.path.join(self.tempcompdir, 'garbage.zck')),
             mock.call().compress_and_fill(mock_cr.SHA256, mock_cr.ZCK_COMPRESSION),
             mock.call().compress_and_fill().rename_file()])
        rec = mock_cr.RepomdRecord.return_value
        rec_comp = rec.compress_and_fill.return_value
        # The last comp_type added is the _zck one
        self.assertEqual(rec_comp.type, 'garbage_zck')
        self.assertEqual(
            mock_cr.Repomd.return_value.set_record.mock_calls,
            [mock.call(rec_comp), mock.call(rec_comp)])

        with open(os.path.join(self.tempcompdir, 'repomd.xml')) as repomd_file:
            repomd_contents = repomd_file.read()

        self.assertEqual(repomd_contents, 'test data')
        self.assertFalse(os.path.exists(os.path.join(self.tempcompdir, 'garbage.zck')))

    @mock.patch('bodhi.server.metadata.cr')
    def test_zchunk_metadata_coverage_zchunk_skipped(self, mock_cr):
        """
        Let's test that we skip zchunk files, because we don't want to zchunk zchunk files.

        This test makes sure we reach 100% coverage by mocking createrepo.

        cr.ZCK_COMPRESSION is only defined when createrepo_c supports zchunk, but createrepo_c's
        zchunk support is only available in createrepo_c >= 0.12.0, and it is also a build flag,
        so we can't be sure that the createrepo_c we work with has that feature.

        This function is designed to *only* make sure we reach 100% coverage and isn't meant
        to test whether zchunk is working correctly.  _test_extended_metadata will take care
        of testing both the regular and zchunked updateinfo if zchunk is enabled
        """
        mock_cr.ZCK_COMPRESSION = 99
        mock_repomd = mock.MagicMock()
        mock_repomd.xml_dump = mock.MagicMock(return_value="test data")
        mock_cr.Repomd = mock.MagicMock(return_value=mock_repomd)

        bodhi_metadata.insert_in_repo(99, self.tempcompdir, 'garbage', 'zck', '/dev/null', True)

        mock_cr.Repomd.assert_called_once_with(os.path.join(self.tempcompdir, 'repomd.xml'))
        mock_cr.RepomdRecord.assert_called_once_with('garbage',
                                                     os.path.join(self.tempcompdir, 'garbage.zck'))
        rec = mock_cr.RepomdRecord.return_value
        rec.compress_and_fill.assert_called_once_with(mock_cr.SHA256, mock_cr.ZCK_COMPRESSION)
        rec_comp = rec.compress_and_fill.return_value
        rec_comp.rename_file.assert_called_once_with()
        self.assertEqual(rec_comp.type, 'garbage')
        mock_cr.Repomd.return_value.set_record.assert_called_once_with(rec_comp)

        with open(os.path.join(self.tempcompdir, 'repomd.xml')) as repomd_file:
            repomd_contents = repomd_file.read()

        self.assertEqual(repomd_contents, 'test data')
        self.assertFalse(os.path.exists(os.path.join(self.tempcompdir, 'garbage.zck')))

    @mock.patch('bodhi.server.metadata.cr')
    def test_zchunk_metadata_coverage_zchunk_unsupported(self, mock_cr):
        """
        Let's test that we skip zchunk compression when it is unsupported by createrepo_c.

        This test makes sure we reach 100% coverage by mocking createrepo.

        cr.ZCK_COMPRESSION is only defined when createrepo_c supports zchunk, but createrepo_c's
        zchunk support is only available in createrepo_c >= 0.12.0, and it is also a build flag,
        so we can't be sure that the createrepo_c we work with has that feature.

        This function is designed to *only* make sure we reach 100% coverage and isn't meant
        to test whether zchunk is working correctly.  _test_extended_metadata will take care
        of testing both the regular and zchunked updateinfo if zchunk is enabled
        """
        del mock_cr.ZCK_COMPRESSION
        mock_repomd = mock.MagicMock()
        mock_repomd.xml_dump = mock.MagicMock(return_value="test data")
        mock_cr.Repomd = mock.MagicMock(return_value=mock_repomd)

        bodhi_metadata.insert_in_repo(bodhi_metadata.cr.XZ_COMPRESSION, self.tempcompdir,
                                      'garbage', 'xz', '/dev/null', True)

        mock_cr.Repomd.assert_called_once_with(os.path.join(self.tempcompdir, 'repomd.xml'))
        mock_cr.RepomdRecord.assert_called_once_with('garbage',
                                                     os.path.join(self.tempcompdir, 'garbage.xz'))
        rec = mock_cr.RepomdRecord.return_value
        rec.compress_and_fill.assert_called_once_with(mock_cr.SHA256, mock_cr.XZ_COMPRESSION)
        rec_comp = rec.compress_and_fill.return_value
        rec_comp.rename_file.assert_called_once_with()
        # The last inserted type is without _zck
        self.assertEqual(rec_comp.type, 'garbage')
        mock_cr.Repomd.return_value.set_record.assert_called_once_with(rec_comp)

        with open(os.path.join(self.tempcompdir, 'repomd.xml')) as repomd_file:
            repomd_contents = repomd_file.read()

        self.assertEqual(repomd_contents, 'test data')
        self.assertFalse(os.path.exists(os.path.join(self.tempcompdir, 'garbage.zck')))
