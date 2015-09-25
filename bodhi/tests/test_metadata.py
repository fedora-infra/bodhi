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

import os
import glob
import shutil
import tempfile
import unittest

from datetime import datetime
from hashlib import sha256
from os.path import join, exists, basename
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension

import createrepo_c

from bodhi import log
from bodhi.config import config
from bodhi.util import mkmetadatadir
from bodhi.models import (Package, Update, Build, Base,
        UpdateRequest, UpdateStatus, UpdateType)
from bodhi.buildsys import get_session, DevBuildsys
from bodhi.metadata import ExtendedMetadata
from bodhi.tests.functional.base import DB_PATH

from bodhi.tests import populate


class TestExtendedMetadata(unittest.TestCase):

    def __init__(self, *args, **kw):
        super(TestExtendedMetadata, self).__init__(*args, **kw)
        repo_path = os.path.join(config.get('mash_dir'), 'f17-updates-testing')
        if not os.path.exists(repo_path):
            os.makedirs(repo_path)

    def setUp(self):
        engine = create_engine(DB_PATH)
        Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
        Session.configure(bind=engine)
        log.debug('Creating all models for %s' % engine)
        Base.metadata.bind = engine
        Base.metadata.create_all(engine)
        self.db = Session()
        populate(self.db)

        # Initialize our temporary repo
        self.tempdir = tempfile.mkdtemp('bodhi')
        self.temprepo = join(self.tempdir, 'f17-updates-testing')
        mkmetadatadir(join(self.temprepo, 'f17-updates-testing', 'i386'))
        self.repodata = join(self.temprepo, 'f17-updates-testing', 'i386', 'repodata')
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

    def tearDown(self):
        self.db.close()
        get_session().clear()
        shutil.rmtree(self.tempdir)

    def _verify_updateinfo(self, repodata):
        updateinfos = glob.glob(join(repodata, "*-updateinfo.xml*"))
        assert len(updateinfos) == 1, "We generated %d updateinfo metadata" % len(updateinfos)
        updateinfo = updateinfos[0]
        hash = basename(updateinfo).split("-", 1)[0]
        hashed = sha256(open(updateinfo).read()).hexdigest()
        assert hash == hashed, "File: %s\nHash: %s" % (basename(updateinfo), hashed)
        return updateinfo

    def get_notice(self, uinfo, title):
        for record in uinfo.updates:
            if record.title == title:
                return record

    def test_extended_metadata(self):
        update = self.db.query(Update).one()

        # Pretend it's pushed to testing
        update.status = UpdateStatus.testing
        update.request = None
        update.date_pushed = datetime.utcnow()
        DevBuildsys.__tagged__[update.title] = ['f17-updates-testing']

        # Generate the XML
        md = ExtendedMetadata(update.release, update.request, self.db, self.temprepo)

        # Insert the updateinfo.xml into the repository
        md.insert_updateinfo()
        updateinfo = self._verify_updateinfo(self.repodata)

        # Read an verify the updateinfo.xml.gz
        uinfo = createrepo_c.UpdateInfo(updateinfo)
        notice = self.get_notice(uinfo, 'mutt-1.5.14-1.fc13')
        self.assertIsNone(notice)

        self.assertEquals(len(uinfo.updates), 1)
        notice = uinfo.updates[0]

        self.assertIsNotNone(notice)
        self.assertEquals(notice.title, update.title)
        self.assertEquals(notice.release, update.release.long_name)
        self.assertEquals(notice.status, update.status.value)
        if update.date_modified:
            self.assertEquals(notice.updated_date, update.date_modified)
        self.assertEquals(notice.fromstr, config.get('bodhi_email'))
        self.assertEquals(notice.rights, config.get('updateinfo_rights'))
        self.assertEquals(notice.description, update.notes)
        #self.assertIsNotNone(notice.issued_date)
        self.assertEquals(notice.id, update.alias)
        bug = notice.references[0]
        self.assertEquals(bug.href, update.bugs[0].url)
        self.assertEquals(bug.id, '12345')
        self.assertEquals(bug.type, 'bugzilla')
        cve = notice.references[1]
        self.assertEquals(cve.type, 'cve')
        self.assertEquals(cve.href, update.cves[0].url)
        self.assertEquals(cve.id, update.cves[0].cve_id)

        col = notice.collections[0]
        self.assertEquals(col.name, update.release.long_name)
        self.assertEquals(col.shortname, update.release.name)

        pkg = col.packages[0]
        self.assertEquals(pkg.epoch, '0')
        self.assertEquals(pkg.name, 'TurboGears')
        self.assertEquals(pkg.src, 'https://download.fedoraproject.org/pub/fedora/linux/updates/testing/17/SRPMS/T/TurboGears-1.0.2.2-2.fc7.src.rpm')
        self.assertEquals(pkg.version, '1.0.2.2')
        self.assertFalse(pkg.reboot_suggested)
        self.assertEquals(pkg.arch, 'src')
        self.assertEquals(pkg.filename, 'TurboGears-1.0.2.2-2.fc7.src.rpm')

    def test_extended_metadata_updating(self):
        update = self.db.query(Update).one()

        # Pretend it's pushed to testing
        update.status = UpdateStatus.testing
        update.request = None
        update.date_pushed = datetime.utcnow()
        DevBuildsys.__tagged__[update.title] = ['f17-updates-testing']

        # Generate the XML
        md = ExtendedMetadata(update.release, update.request, self.db, self.temprepo)

        # Insert the updateinfo.xml into the repository
        md.insert_updateinfo()
        md.cache_repodata()

        updateinfo = self._verify_updateinfo(self.repodata)

        # Read an verify the updateinfo.xml.gz
        uinfo = createrepo_c.UpdateInfo(updateinfo)
        notice = self.get_notice(uinfo, update.title)

        self.assertIsNotNone(notice)
        self.assertEquals(notice.title, update.title)
        self.assertEquals(notice.release, update.release.long_name)
        self.assertEquals(notice.status, update.status.value)
        self.assertEquals(notice.updated_date, update.date_modified)
        self.assertEquals(notice.fromstr, config.get('bodhi_email'))
        self.assertEquals(notice.description, update.notes)
        #self.assertIsNotNone(notice.issued_date)
        self.assertEquals(notice.id, update.alias)
        #self.assertIsNone(notice.epoch)
        bug = notice.references[0]
        url = update.bugs[0].url
        self.assertEquals(bug.href, url)
        self.assertEquals(bug.id, '12345')
        self.assertEquals(bug.type, 'bugzilla')
        cve = notice.references[1]
        self.assertEquals(cve.type, 'cve')
        self.assertEquals(cve.href, update.cves[0].url)
        self.assertEquals(cve.id, update.cves[0].cve_id)

        # Change the notes on the update, but not the date_modified, so we can
        # ensure that the notice came from the cache
        update.notes = u'x'

        # Re-initialize our temporary repo
        shutil.rmtree(self.temprepo)
        os.mkdir(self.temprepo)
        mkmetadatadir(join(self.temprepo, 'f17-updates-testing', 'i386'))

        md = ExtendedMetadata(update.release, update.request, self.db, self.temprepo)
        md.insert_updateinfo()
        updateinfo = self._verify_updateinfo(self.repodata)

        # Read an verify the updateinfo.xml.gz
        uinfo = createrepo_c.UpdateInfo(updateinfo)
        notice = self.get_notice(uinfo, update.title)

        self.assertIsNotNone(notice)
        self.assertEquals(notice.description, u'Useful details!')  # not u'x'

    def test_metadata_updating_with_edited_update(self):
        update = self.db.query(Update).one()

        # Pretend it's pushed to testing
        update.status = UpdateStatus.testing
        update.request = None
        update.date_pushed = datetime.utcnow()
        DevBuildsys.__tagged__[update.title] = ['f17-updates-testing']

        # Generate the XML
        md = ExtendedMetadata(update.release, update.request, self.db, self.temprepo)

        # Insert the updateinfo.xml into the repository
        md.insert_updateinfo()
        md.cache_repodata()

        updateinfo = self._verify_updateinfo(self.repodata)

        # Read an verify the updateinfo.xml.gz
        uinfo = createrepo_c.UpdateInfo(updateinfo)
        notice = self.get_notice(uinfo, update.title)

        self.assertIsNotNone(notice)
        self.assertEquals(notice.title, update.title)
        self.assertEquals(notice.release, update.release.long_name)
        self.assertEquals(notice.status, update.status.value)
        self.assertEquals(notice.updated_date, update.date_modified)
        self.assertEquals(notice.fromstr, config.get('bodhi_email'))
        self.assertEquals(notice.description, update.notes)
        self.assertIsNotNone(notice.issued_date)
        self.assertEquals(notice.id, update.alias)
        #self.assertIsNone(notice.epoch)
        bug = notice.references[0]
        self.assertEquals(bug.href, update.bugs[0].url)
        self.assertEquals(bug.id, '12345')
        self.assertEquals(bug.type, 'bugzilla')
        cve = notice.references[1]
        self.assertEquals(cve.type, 'cve')
        self.assertEquals(cve.href, update.cves[0].url)
        self.assertEquals(cve.id, update.cves[0].cve_id)

        # Change the notes on the update *and* the date_modified
        update.notes = u'x'
        update.date_modified = datetime.utcnow()

        # Re-initialize our temporary repo
        shutil.rmtree(self.temprepo)
        os.mkdir(self.temprepo)
        mkmetadatadir(join(self.temprepo, 'f17-updates-testing', 'i386'))

        md = ExtendedMetadata(update.release, update.request, self.db, self.temprepo)
        md.insert_updateinfo()
        updateinfo = self._verify_updateinfo(self.repodata)

        # Read an verify the updateinfo.xml.gz
        uinfo = createrepo_c.UpdateInfo(updateinfo)
        notice = self.get_notice(uinfo, update.title)

        self.assertIsNotNone(notice)
        self.assertEquals(notice.description, u'x')
        self.assertEquals(notice.updated_date.strftime('%Y-%m-%d %H:%M:%S'),
                          update.date_modified.strftime('%Y-%m-%d %H:%M:%S'))

    def test_metadata_updating_with_old_stable_security(self):
        update = self.db.query(Update).one()
        update.request = None
        update.type = UpdateType.security
        update.status = UpdateStatus.stable
        update.date_pushed = datetime.utcnow()
        DevBuildsys.__tagged__[update.title] = ['f17-updates']

        repo = join(self.tempdir, 'f17-updates')
        mkmetadatadir(join(repo, 'f17-updates', 'i386'))
        self.repodata = join(repo, 'f17-updates', 'i386', 'repodata')

        # Generate the XML
        md = ExtendedMetadata(update.release, UpdateRequest.stable,
                              self.db, repo)

        # Insert the updateinfo.xml into the repository
        md.insert_updateinfo()
        md.cache_repodata()

        updateinfo = self._verify_updateinfo(self.repodata)

        # Read an verify the updateinfo.xml.gz
        uinfo = createrepo_c.UpdateInfo(updateinfo)
        notice = self.get_notice(uinfo, update.title)
        self.assertIsNotNone(notice)

        # Create a new non-security update for the same package
        newbuild = 'bodhi-2.0-2.fc17'
        pkg = self.db.query(Package).filter_by(name=u'bodhi').one()
        build = Build(nvr=newbuild, package=pkg)
        self.db.add(build)
        self.db.flush()
        newupdate = Update(title=newbuild,
                           type=UpdateType.enhancement,
                           status=UpdateStatus.stable,
                           request=None,
                           release=update.release,
                           builds=[build],
                           notes=u'x')
        newupdate.assign_alias()
        self.db.add(newupdate)
        self.db.flush()

        # Untag the old security build
        DevBuildsys.__untag__.append(update.title)
        DevBuildsys.__tagged__[newupdate.title] = [newupdate.release.stable_tag]
        buildrpms = DevBuildsys.__rpms__[0].copy()
        buildrpms['nvr'] = 'bodhi-2.0-2.fc17'
        buildrpms['release'] = '2.fc17'
        DevBuildsys.__rpms__.append(buildrpms)

        # Re-initialize our temporary repo
        shutil.rmtree(repo)
        os.mkdir(repo)
        mkmetadatadir(join(repo, 'f17-updates', 'i386'))

        md = ExtendedMetadata(update.release, UpdateRequest.stable, self.db, repo)
        md.insert_updateinfo()
        updateinfo = self._verify_updateinfo(self.repodata)

        # Read an verify the updateinfo.xml.gz
        uinfo = createrepo_c.UpdateInfo(updateinfo)

        self.assertEquals(len(uinfo.updates), 2)

        notice = self.get_notice(uinfo, 'bodhi-2.0-1.fc17')
        self.assertIsNotNone(notice)
        notice = self.get_notice(uinfo, 'bodhi-2.0-2.fc17')
        self.assertIsNotNone(notice)

    def test_metadata_updating_with_old_testing_security(self):
        update = self.db.query(Update).one()
        update.request = None
        update.type = UpdateType.security
        update.status = UpdateStatus.testing
        update.date_pushed = datetime.utcnow()
        DevBuildsys.__tagged__[update.title] = ['f17-updates-testing']

        # Generate the XML
        md = ExtendedMetadata(update.release, UpdateRequest.testing,
                              self.db, self.temprepo)

        # Insert the updateinfo.xml into the repository
        md.insert_updateinfo()
        md.cache_repodata()

        updateinfo = self._verify_updateinfo(self.repodata)

        # Read an verify the updateinfo.xml.gz
        uinfo = createrepo_c.UpdateInfo(updateinfo)
        notice = self.get_notice(uinfo, update.title)
        self.assertIsNotNone(notice)

        # Create a new non-security update for the same package
        newbuild = 'bodhi-2.0-2.fc17'
        pkg = self.db.query(Package).filter_by(name=u'bodhi').one()
        build = Build(nvr=newbuild, package=pkg)
        self.db.add(build)
        self.db.flush()
        newupdate = Update(title=newbuild,
                           type=UpdateType.enhancement,
                           status=UpdateStatus.testing,
                           request=None,
                           release=update.release,
                           builds=[build],
                           notes=u'x')
        newupdate.assign_alias()
        self.db.add(newupdate)
        self.db.flush()

        # Untag the old security build
        del(DevBuildsys.__tagged__[update.title])
        DevBuildsys.__untag__.append(update.title)
        DevBuildsys.__tagged__[newupdate.title] = [newupdate.release.testing_tag]
        buildrpms = DevBuildsys.__rpms__[0].copy()
        buildrpms['nvr'] = 'bodhi-2.0-2.fc17'
        buildrpms['release'] = '2.fc17'
        DevBuildsys.__rpms__.append(buildrpms)
        del(DevBuildsys.__rpms__[0])

        # Re-initialize our temporary repo
        shutil.rmtree(self.temprepo)
        os.mkdir(self.temprepo)
        mkmetadatadir(join(self.temprepo, 'f17-updates-testing', 'i386'))

        md = ExtendedMetadata(update.release, UpdateRequest.testing,
                              self.db, self.temprepo)
        md.insert_updateinfo()
        updateinfo = self._verify_updateinfo(self.repodata)

        # Read an verify the updateinfo.xml.gz
        uinfo = createrepo_c.UpdateInfo(updateinfo)

        self.assertEquals(len(uinfo.updates), 1)
        notice = self.get_notice(uinfo, 'bodhi-2.0-1.fc17')
        self.assertIsNone(notice)
        notice = self.get_notice(uinfo, 'bodhi-2.0-2.fc17')
        self.assertIsNotNone(notice)
