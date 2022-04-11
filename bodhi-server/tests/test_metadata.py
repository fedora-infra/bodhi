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

from datetime import datetime
from hashlib import sha256
from os.path import basename, exists, join
from unittest import mock
import glob
import os
import shutil
import tempfile

import createrepo_c

from bodhi.server.buildsys import DevBuildsys, setup_buildsystem, teardown_buildsystem
from bodhi.server.config import config
from bodhi.server.metadata import UpdateInfoMetadata
from bodhi.server.models import Release, Update, UpdateRequest, UpdateStatus
import bodhi.server.metadata as bodhi_metadata

from . import base


class UpdateInfoMetadataTestCase(base.BasePyTestCase):
    def setup_method(self, method):
        """
        Initialize our temporary repo.
        """
        super().setup_method(method)
        setup_buildsystem({'buildsystem': 'dev'})
        self.tempdir = tempfile.mkdtemp('bodhi')
        self.tempcompdir = join(self.tempdir, 'f17-updates-testing')
        self.temprepo = join(self.tempcompdir, 'compose', 'Everything', 'i386', 'os')
        base.mkmetadatadir(join(self.temprepo, 'f17-updates-testing', 'i386'), updateinfo=False)
        config['cache_dir'] = os.path.join(self.tempdir, 'cache')
        os.makedirs(config['cache_dir'])

    def teardown_method(self, method):
        """
        Clean up the tempdir.
        """
        super().teardown_method(method)
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

        assert len(md.uinfo.updates) == 1
        assert md.uinfo.updates[0].title == update.title
        assert md.uinfo.updates[0].release == update.release.long_name
        assert md.uinfo.updates[0].status == update.status.value
        assert md.uinfo.updates[0].updated_date == update.date_modified
        assert md.uinfo.updates[0].fromstr == config.get('bodhi_email')
        assert md.uinfo.updates[0].rights == config.get('updateinfo_rights')
        assert md.uinfo.updates[0].description == update.notes
        assert md.uinfo.updates[0].id == update.alias
        assert md.uinfo.updates[0].severity == 'Moderate'
        assert len(md.uinfo.updates[0].references) == 1
        bug = md.uinfo.updates[0].references[0]
        assert bug.href == update.bugs[0].url
        assert bug.id == '12345'
        assert bug.type == 'bugzilla'
        assert len(md.uinfo.updates[0].collections) == 1
        col = md.uinfo.updates[0].collections[0]
        assert col.name == update.release.long_name
        assert col.shortname == update.release.name
        assert len(col.packages) == 2
        pkg = col.packages[0]
        assert pkg.epoch == '0'
        # It's a little goofy, but the DevBuildsys is going to return TurboGears rpms when its
        # listBuildRPMs() method is called, so let's just roll with it.
        assert pkg.name == 'TurboGears'
        assert pkg.src == \
            ('https://download.fedoraproject.org/pub/fedora/linux/updates/17/SRPMS/T/'
             'TurboGears-1.0.2.2-2.fc17.src.rpm')
        assert pkg.version == '1.0.2.2'
        assert not pkg.reboot_suggested
        assert not pkg.relogin_suggested
        assert pkg.arch == 'src'
        assert pkg.filename == 'TurboGears-1.0.2.2-2.fc17.src.rpm'
        pkg = col.packages[1]
        assert pkg.epoch == '0'
        assert pkg.name == 'TurboGears'
        assert pkg.src == \
            ('https://download.fedoraproject.org/pub/fedora/linux/updates/17/i386/T/'
             'TurboGears-1.0.2.2-2.fc17.noarch.rpm')
        assert pkg.version == '1.0.2.2'
        assert not pkg.reboot_suggested
        assert not pkg.relogin_suggested
        assert pkg.arch == 'noarch'
        assert pkg.filename == 'TurboGears-1.0.2.2-2.fc17.noarch.rpm'

    def test_date_modified_none(self):
        """The metadata should use date_submitted if an update's date_modified is None."""
        update = self.db.query(Update).one()
        update.date_modified = None
        md = UpdateInfoMetadata(update.release, update.request, self.db, self.temprepo,
                                close_shelf=False)
        md.add_update(update)
        md.shelf.close()

        assert len(md.uinfo.updates) == 1
        assert md.uinfo.updates[0].updated_date == update.date_submitted

    def test_date_pushed_none(self):
        """The metadata should use date_submitted if an update's date_pushed is None."""
        update = self.db.query(Update).one()
        update.date_pushed = None
        md = UpdateInfoMetadata(update.release, update.request, self.db, self.temprepo,
                                close_shelf=False)
        md.add_update(update)
        md.shelf.close()

        assert len(md.uinfo.updates) == 1
        assert md.uinfo.updates[0].issued_date == update.date_submitted

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
        assert len(col.packages) == 1
        pkg = col.packages[0]
        assert pkg.src == \
            ('https://download.fedoraproject.org/pub/fedora/linux/updates/17/aarch64/T/'
             'TurboGears-1.0.2.2-2.fc17.aarch64.rpm')

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
        assert len(col.packages) == 1
        pkg = col.packages[0]
        assert pkg.epoch == '42'


class TestFetchUpdates(UpdateInfoMetadataTestCase):
    """Test the UpdateInfoMetadata._fetch_updates() method."""

    @mock.patch('bodhi.server.metadata.log.warning')
    def test_build_unassociated(self, warning):
        """A warning should be logged if the Bodhi Build object is not associated with an Update."""
        update = self.db.query(Update).one()
        update.date_pushed = None
        u = base.create_update(self.db, ['TurboGears-1.0.2.2-4.fc17'])
        u.builds[0].update = None
        self.db.flush()

        # _fetch_updates() is called as part of UpdateInfoMetadata.__init__() so we'll just
        # instantiate one.
        md = UpdateInfoMetadata(update.release, update.request, self.db, self.temprepo,
                                close_shelf=False)

        warning.assert_called_once_with(
            'TurboGears-1.0.2.2-4.fc17 does not have a corresponding update')
        # Since the Build didn't have an Update, no Update should have been added to md.updates.
        assert md.updates == set([])


class TestUpdateInfoMetadata(UpdateInfoMetadataTestCase):

    def setup_method(self, method):
        super().setup_method(method)

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
        assert exists(join(self.repodata, 'repomd.xml'))

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

    def teardown_method(self, method):
        config['compose_stage_dir'] = self._compose_stage_dir
        config['compose_dir'] = self._compose_dir
        config['cache_dir'] = None
        shutil.rmtree(self._new_compose_stage_dir)
        super().teardown_method(method)

    def _verify_updateinfos(self, repodata):
        updateinfos = glob.glob(join(repodata, "*-updateinfo.xml*"))
        if hasattr(createrepo_c, 'ZCK_COMPRESSION'):
            assert len(updateinfos) == 2, f"We generated {len(updateinfos)} updateinfo metadata"
        else:
            assert len(updateinfos) == 1, f"We generated {len(updateinfos)} updateinfo metadata"
        for updateinfo in updateinfos:
            hash = basename(updateinfo).split("-", 1)[0]
            with open(updateinfo, 'rb') as fn:
                hashed = sha256(fn.read()).hexdigest()
            assert hash == hashed, f"File: {basename(updateinfo)}\nHash: {hashed}"

        return updateinfos

    def get_notice(self, uinfo, title):
        for record in uinfo.updates:
            if record.title == title:
                return record

    def test___init___uses_bz2_for_epel(self):
        """Assert that the __init__() method sets the comp_type attribute to cr.BZ2 for EPEL."""
        epel_7 = Release(id_prefix="FEDORA-EPEL", stable_tag='epel7')

        md = UpdateInfoMetadata(epel_7, UpdateRequest.stable, self.db, self.tempdir)

        assert md.comp_type == createrepo_c.BZ2
        assert not md.zchunk

    def test___init___uses_xz_for_fedora(self):
        """Assert that the __init__() method sets the comp_type attribute to cr.XZ for Fedora."""
        fedora = Release.query.one()

        md = UpdateInfoMetadata(fedora, UpdateRequest.stable, self.db, self.tempdir)

        assert md.comp_type == createrepo_c.XZ
        assert md.zchunk

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
            assert notice is None

            assert len(uinfo.updates) == 1
            notice = uinfo.updates[0]

            assert notice is not None
            assert notice.title == update.title
            assert notice.release == update.release.long_name
            assert notice.status == update.status.value
            if update.date_modified:
                assert notice.updated_date == update.date_modified
            assert notice.fromstr == config.get('bodhi_email')
            assert notice.rights == config.get('updateinfo_rights')
            assert notice.description == update.notes
            assert notice.id == update.alias
            assert notice.severity == 'Moderate'
            bug = notice.references[0]
            assert bug.href == update.bugs[0].url
            assert bug.id == '12345'
            assert bug.type == 'bugzilla'

            col = notice.collections[0]
            assert col.name == update.release.long_name
            assert col.shortname == update.release.name

            pkg = col.packages[0]
            assert pkg.epoch == '0'
            assert pkg.name == 'TurboGears'
            assert pkg.src == \
                ('https://download.fedoraproject.org/pub/fedora/linux/updates/testing/17/SRPMS/T/'
                 'TurboGears-1.0.2.2-2.fc17.src.rpm')
            assert pkg.version == '1.0.2.2'
            assert not pkg.reboot_suggested
            assert not pkg.relogin_suggested
            assert pkg.arch == 'src'
            assert pkg.filename == 'TurboGears-1.0.2.2-2.fc17.src.rpm'

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
        assert mock_cr.RepomdRecord.mock_calls == \
            [mock.call('garbage', os.path.join(self.tempcompdir, 'garbage.zck')),
             mock.call().compress_and_fill(mock_cr.SHA256, mock_cr.XZ_COMPRESSION),
             mock.call().compress_and_fill().rename_file(),
             mock.call('garbage_zck', os.path.join(self.tempcompdir, 'garbage.zck')),
             mock.call().compress_and_fill(mock_cr.SHA256, mock_cr.ZCK_COMPRESSION),
             mock.call().compress_and_fill().rename_file()]
        rec = mock_cr.RepomdRecord.return_value
        rec_comp = rec.compress_and_fill.return_value
        # The last comp_type added is the _zck one
        assert rec_comp.type == 'garbage_zck'
        assert mock_cr.Repomd.return_value.set_record.mock_calls == \
            [mock.call(rec_comp), mock.call(rec_comp)]

        with open(os.path.join(self.tempcompdir, 'repomd.xml')) as repomd_file:
            repomd_contents = repomd_file.read()

        assert repomd_contents == 'test data'
        assert not os.path.exists(os.path.join(self.tempcompdir, 'garbage.zck'))

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
        assert rec_comp.type == 'garbage'
        mock_cr.Repomd.return_value.set_record.assert_called_once_with(rec_comp)

        with open(os.path.join(self.tempcompdir, 'repomd.xml')) as repomd_file:
            repomd_contents = repomd_file.read()

        assert repomd_contents == 'test data'
        assert not os.path.exists(os.path.join(self.tempcompdir, 'garbage.zck'))

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
        assert rec_comp.type == 'garbage'
        mock_cr.Repomd.return_value.set_record.assert_called_once_with(rec_comp)

        with open(os.path.join(self.tempcompdir, 'repomd.xml')) as repomd_file:
            repomd_contents = repomd_file.read()

        assert repomd_contents == 'test data'
        assert not os.path.exists(os.path.join(self.tempcompdir, 'garbage.zck'))
