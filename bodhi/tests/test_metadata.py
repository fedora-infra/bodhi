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

    def setUp(self):
        engine = create_engine(DB_PATH)
        DBSession.configure(bind=engine)
        Base.metadata.create_all(engine)
        self.db = DBSession()
        populate(self.db)

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

        # Initialize our temporary repo
        tempdir = tempfile.mkdtemp('bodhi')
        temprepo = join(tempdir, 'f17-updates-testing')
        print("Inserting updateinfo into temprepo: %s" % temprepo)
        mkmetadatadir(join(temprepo, 'i386'))
        repodata = join(temprepo, 'i386', 'repodata')
        assert exists(join(repodata, 'repomd.xml'))

        # Generate the XML
        md = ExtendedMetadata(update.release, update.request, self.db, tempdir)

        repo_path = os.path.join(config.get('mashed_dir'), 'f17-updates-testing')
        if not os.path.exists(repo_path):
            os.makedirs(repo_path)

        # Insert the updateinfo.xml into the repository
        md.insert_updateinfo()
        updateinfo = self._verify_updateinfo(repodata)

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

        # Clean up
        shutil.rmtree(tempdir)
