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
from yum.update_md import UpdateMetadata

from bodhi import log
from bodhi.config import config
from bodhi.util import mkmetadatadir, get_nvr
from bodhi.models import (Release, Package, Update, Bug, Build, Base,
        DBSession, UpdateRequest, UpdateStatus)
from bodhi.buildsys import get_session, DevBuildsys
from bodhi.metadata import ExtendedMetadata
from bodhi.tests.functional.base import DB_PATH

from bodhi.tests import populate


class TestExtendedMetadata(unittest.TestCase):

    def __init__(self, *args, **kw):
        super(TestExtendedMetadata, self).__init__(*args, **kw)
        repo_path = os.path.join(config.get('mashed_dir'), 'f17-updates-testing')
        if not os.path.exists(repo_path):
            os.makedirs(repo_path)

    def setUp(self):
        engine = create_engine(DB_PATH)
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        self.db = DBSession()
        populate(self.db)

        # Initialize our temporary repo
        self.tempdir = tempfile.mkdtemp('bodhi')
        self.temprepo = join(self.tempdir, 'f17-updates-testing')
        mkmetadatadir(join(self.temprepo, 'i386'))
        self.repodata = join(self.temprepo, 'i386', 'repodata')
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
        DBSession.remove()
        get_session().clear()
        shutil.rmtree(self.tempdir)

    def _verify_updateinfo(self, repodata):
        updateinfos = glob.glob(join(repodata, "*-updateinfo.xml.gz"))
        assert len(updateinfos) == 1, "We generated %d updateinfo metadata" % len(updateinfos)
        updateinfo = updateinfos[0]
        hash = basename(updateinfo).split("-", 1)[0]
        hashed = sha256(open(updateinfo).read()).hexdigest()
        assert hash == hashed, "File: %s\nHash: %s" % (basename(updateinfo), hashed)
        return updateinfo

    def test_extended_metadata(self):
        update = self.db.query(Update).one()

        # Pretend it's pushed to testing
        update.assign_alias()
        update.status = UpdateStatus.testing
        update.request = None
        DevBuildsys.__tagged__[update.title] = ['f17-updates-testing']

        # Generate the XML
        md = ExtendedMetadata(update.release, update.request, self.db, self.tempdir)

        # Insert the updateinfo.xml into the repository
        md.insert_updateinfo()
        updateinfo = self._verify_updateinfo(self.repodata)

        # Read an verify the updateinfo.xml.gz
        uinfo = UpdateMetadata()
        uinfo.add(updateinfo)
        notice = uinfo.get_notice(('mutt', '1.5.14', '1.fc13'))
        self.assertIsNone(notice)

        notices = uinfo.get_notices()
        self.assertEquals(len(notices), 1)
        notice = notices[0]

        self.assertIsNotNone(notice)
        self.assertEquals(notice['title'], update.title)
        self.assertEquals(notice['release'], update.release.long_name)
        self.assertEquals(notice['status'], update.status.value)
        self.assertEquals(notice['updated'], update.date_modified)
        self.assertEquals(notice['from'], str(config.get('bodhi_email')))
        self.assertEquals(notice['description'], update.notes)
        self.assertIsNotNone(notice['issued'])
        self.assertEquals(notice['update_id'], update.alias)
        self.assertIsNone(notice['epoch'])
        cve = notice['references'][0]
        self.assertIsNone(cve['title'])
        self.assertEquals(cve['type'], 'cve')
        self.assertEquals(cve['href'], update.cves[0].url)
        self.assertEquals(cve['id'], update.cves[0].cve_id)
        bug = notice['references'][1]
        self.assertEquals(bug['href'], update.bugs[0].url)
        self.assertEquals(bug['id'], '12345')
        self.assertEquals(bug['type'], 'bugzilla')

    def test_extended_metadata_updating(self):
        update = self.db.query(Update).one()

        # Pretend it's pushed to testing
        update.assign_alias()
        update.status = UpdateStatus.testing
        update.request = None
        DevBuildsys.__tagged__[update.title] = ['f17-updates-testing']

        # Generate the XML
        md = ExtendedMetadata(update.release, update.request, self.db, self.tempdir)

        # Insert the updateinfo.xml into the repository
        md.insert_updateinfo()
        md.cache_repodata()

        updateinfo = self._verify_updateinfo(self.repodata)

        # Read an verify the updateinfo.xml.gz
        uinfo = UpdateMetadata()
        uinfo.add(updateinfo)
        notice = uinfo.get_notice(('mutt', '1.5.14', '1.fc13'))
        self.assertIsNone(notice)

        notice = uinfo.get_notice(get_nvr(update.title))

        self.assertIsNotNone(notice)
        self.assertEquals(notice['title'], update.title)
        self.assertEquals(notice['release'], update.release.long_name)
        self.assertEquals(notice['status'], update.status.value)
        self.assertEquals(notice['updated'], update.date_modified)
        self.assertEquals(notice['from'], str(config.get('bodhi_email')))
        self.assertEquals(notice['description'], update.notes)
        self.assertIsNotNone(notice['issued'])
        self.assertEquals(notice['update_id'], update.alias)
        self.assertIsNone(notice['epoch'])
        cve = notice['references'][0]
        self.assertIsNone(cve['title'])
        self.assertEquals(cve['type'], 'cve')
        self.assertEquals(cve['href'], update.cves[0].url)
        self.assertEquals(cve['id'], update.cves[0].cve_id)
        bug = notice['references'][1]
        self.assertEquals(bug['href'], update.bugs[0].url)
        self.assertEquals(bug['id'], '12345')
        self.assertEquals(bug['type'], 'bugzilla')

        # Change the notes on the update, but not the date_modified, so we can
        # ensure that the notice came from the cache
        update.notes = u'x'

        # Re-initialize our temporary repo
        shutil.rmtree(self.temprepo)
        os.mkdir(self.temprepo)
        mkmetadatadir(join(self.temprepo, 'i386'))

        md = ExtendedMetadata(update.release, update.request, self.db, self.tempdir)
        md.insert_updateinfo()
        updateinfo = self._verify_updateinfo(self.repodata)

        # Read an verify the updateinfo.xml.gz
        uinfo = UpdateMetadata()
        uinfo.add(updateinfo)

        notice = uinfo.get_notice(get_nvr(update.title))
        self.assertIsNotNone(notice)
        self.assertEquals(notice['description'], u'Useful details!')  # not u'x'
        self.assertEquals(notice['title'], update.title)
        self.assertEquals(notice['release'], update.release.long_name)
        self.assertEquals(notice['status'], update.status.value)
        self.assertEquals(notice['updated'], update.date_modified)
        self.assertEquals(notice['from'], str(config.get('bodhi_email')))
        self.assertIsNotNone(notice['issued'])
        self.assertEquals(notice['update_id'], update.alias)
        self.assertIsNone(notice['epoch'])
        cve = notice['references'][0]
        self.assertIsNone(cve['title'])
        self.assertEquals(cve['type'], 'cve')
        self.assertEquals(cve['href'], update.cves[0].url)
        self.assertEquals(cve['id'], update.cves[0].cve_id)
        bug = notice['references'][1]
        self.assertEquals(bug['href'], update.bugs[0].url)
        self.assertEquals(bug['id'], '12345')
        self.assertEquals(bug['type'], 'bugzilla')

    def test_metadata_updating_with_edited_update(self):
        update = self.db.query(Update).one()

        # Pretend it's pushed to testing
        update.assign_alias()
        update.status = UpdateStatus.testing
        update.request = None
        DevBuildsys.__tagged__[update.title] = ['f17-updates-testing']

        # Generate the XML
        md = ExtendedMetadata(update.release, update.request, self.db, self.tempdir)

        # Insert the updateinfo.xml into the repository
        md.insert_updateinfo()
        md.cache_repodata()

        updateinfo = self._verify_updateinfo(self.repodata)

        # Read an verify the updateinfo.xml.gz
        uinfo = UpdateMetadata()
        uinfo.add(updateinfo)
        notice = uinfo.get_notice(('mutt', '1.5.14', '1.fc13'))
        self.assertIsNone(notice)

        notice = uinfo.get_notice(get_nvr(update.title))

        self.assertIsNotNone(notice)
        self.assertEquals(notice['title'], update.title)
        self.assertEquals(notice['release'], update.release.long_name)
        self.assertEquals(notice['status'], update.status.value)
        self.assertEquals(notice['updated'], update.date_modified)
        self.assertEquals(notice['from'], str(config.get('bodhi_email')))
        self.assertEquals(notice['description'], update.notes)
        self.assertIsNotNone(notice['issued'])
        self.assertEquals(notice['update_id'], update.alias)
        self.assertIsNone(notice['epoch'])
        cve = notice['references'][0]
        self.assertIsNone(cve['title'])
        self.assertEquals(cve['type'], 'cve')
        self.assertEquals(cve['href'], update.cves[0].url)
        self.assertEquals(cve['id'], update.cves[0].cve_id)
        bug = notice['references'][1]
        self.assertEquals(bug['href'], update.bugs[0].url)
        self.assertEquals(bug['id'], '12345')
        self.assertEquals(bug['type'], 'bugzilla')

        # Change the notes on the update *and* the date_modified
        update.notes = u'x'
        update.date_modified = datetime.utcnow()

        # Re-initialize our temporary repo
        shutil.rmtree(self.temprepo)
        os.mkdir(self.temprepo)
        mkmetadatadir(join(self.temprepo, 'i386'))

        md = ExtendedMetadata(update.release, update.request, self.db, self.tempdir)
        md.insert_updateinfo()
        updateinfo = self._verify_updateinfo(self.repodata)

        # Read an verify the updateinfo.xml.gz
        uinfo = UpdateMetadata()
        uinfo.add(updateinfo)

        notice = uinfo.get_notice(get_nvr(update.title))
        self.assertIsNotNone(notice)
        self.assertEquals(notice['description'], u'x')
        self.assertEquals(notice['updated'],
                update.date_modified.strftime('%Y-%m-%d %H:%M:%S'))
