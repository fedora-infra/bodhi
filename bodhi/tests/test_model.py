# $Id: test_model.py,v 1.5 2006/12/31 09:10:25 lmacken Exp $

import os
import sys
import time
import shutil
import tempfile
import turbogears

from os.path import join, exists, basename
from turbogears import testutil, database, config
from bodhi.util import mkmetadatadir
from bodhi.model import Release, Package, PackageUpdate, Bugzilla, CVE, Arch
from yum.update_md import UpdateMetadata
from sqlobject.dberrors import DuplicateEntryError

database.set_db_uri("sqlite:///:memory:")
turbogears.update_config(configfile='dev.cfg',
                         modulename='bodhi.config')


#class TestEPEL(testutil.DBTest):
    #def test_epel(self):


class TestPackageUpdate(testutil.DBTest):

    def get_pkg(self):
        return Package(name='mutt')

    def get_arches(self):
        self.arches = []
        arches = {
            # arch     subarches
            'i386'   : ['i386', 'i486', 'i586', 'i686', 'athlon', 'noarch'],
            'x86_64' : ['x86_64', 'ia32e', 'noarch'],
            'ppc'    : ['ppc', 'noarch']
        }
        biarches = {
            # arch     compatarches
            'i386'   : [],
            'x86_64' : ['i386', 'i486', 'i586', 'i686', 'athlon'],
            'ppc'    : ['ppc64', 'ppc64iseries']
        }
        for arch in arches.keys():
            self.arches.append(Arch(name=arch, subarches=arches[arch],
                                    compatarches=biarches[arch]))
        return self.arches

    def get_rel(self):
        rel = Release(name='fc7', long_name='Fedora 7', repodir='7',
                      id_prefix='FEDORA')
        map(rel.addArch, self.get_arches())
        return rel

    def get_update(self, name='mutt-1.5.14-1.fc7'):
        update = PackageUpdate(nvr=name, package=self.get_pkg(),
                               release=self.get_rel(), submitter='foo@bar.com',
                               testing=True, type='security',
                               notes='foobar')
        update._build_filelist()
        return update

    def get_bug(self):
        return Bugzilla(bz_id=1)

    def get_cve(self):
        return CVE(cve_id="CVE-2007-0000")

    def test_dupe(self):
        update1 = self.get_update()
        try:
            update2 = self.get_update()
        except DuplicateEntryError:
            return
        assert False

    def test_creation(self):
        update = self.get_update()
        assert update.nvr == 'mutt-1.5.14-1.fc7'
        assert update.package.name == 'mutt'
        assert update.release.name == 'fc7'
        assert update.release.updates[0] == update
        assert update.testing == True
        assert update.type == 'security'
        assert update.notes == 'foobar'
        bug = self.get_bug()
        cve = self.get_cve()
        update.addBugzilla(bug)
        update.addCVE(cve)
        assert update.bugs[0].bz_id == 1
        assert update.cves[0].cve_id == 'CVE-2007-0000'

    def test_id(self):
        update = self.get_update()
        update.assign_id()
        assert update.update_id == 'FEDORA-%s-0001' % time.localtime()[0]

    def test_repo(self):
        update = self.get_update()
        assert update.get_repo() == 'testing/7'

    def test_filelist(self):
        pkg_dir = config.get('build_dir')
        update = self.get_update()
        for arch in ('i386', 'ppc', 'x86_64'):
            assert update.filelist.has_key(arch)
            assert len(update.filelist[arch]) == 2
            assert join(pkg_dir, update.package.name, '1.5.14', '1.fc7',
                        arch, '%s.%s.rpm' % (update.nvr, arch)) in \
                    update.filelist[arch]
            assert join(pkg_dir, update.package.name, '1.5.14', '1.fc7',
                        arch, 'mutt-debuginfo-1.5.14-1.fc7.%s.rpm' % arch) \
                    in update.filelist[arch]
        assert update.filelist.has_key('SRPMS')
        assert len(update.filelist['SRPMS']) == 1
        assert join(pkg_dir, update.package.name, '1.5.14', '1.fc7', 'src',
                    '%s.src.rpm' % update.nvr) in update.filelist['SRPMS']

    def _assert_files(self, update, repo):
        """ Make sure all of the files for this update exist """
        for (arch, files) in update.filelist.items():
            for file in files:
                filename = basename(file)
                if filename.find('debuginfo') != -1:
                    assert exists(join(repo, arch, 'debug', filename))
                elif filename.find('src.rpm') != -1:
                    assert exists(join(repo, 'SRPMS', filename))
                else:
                    assert exists(join(repo, arch, filename))
            assert exists(join(repo, arch, 'repodata', 'updateinfo.xml.gz'))

    def test_push(self):
        from init import init_updates_stage
        push_stage = tempfile.mkdtemp('bodhi')
        update = self.get_update()
        init_updates_stage(stage_dir=push_stage)

        update.request = 'push'
        print "Pushing to temp stage: %s" % push_stage
        for msg in update.run_request(stage=push_stage):
            pass

        # Verify that all files got pushed
        repo = join(push_stage, update.get_repo())
        self._assert_files(update, repo)

        # Verify the updateinfo.xml.gz
        uinfo = UpdateMetadata()
        uinfo.add(join(repo, 'i386', 'repodata', 'updateinfo.xml.gz'))
        notice = uinfo.get_notice(update.nvr)
        from pprint import pprint
        pprint(notice._md)
        assert notice['from'] == 'updates@fedora.redhat.com'
        assert notice['title'] == update.nvr
        assert notice['release'] == update.release.long_name
        assert notice['type'] == update.type
        assert notice['status'] == update.testing and 'testing' or 'final'
        assert notice['update_id'] == update.update_id
        assert notice['issued'] == str(update.date_pushed)
        assert notice['description'] == update.notes
        for collection in notice['pkglist']:
            numfiles = 0
            for archfiles in update.filelist.values():
                for file in archfiles:
                    numfiles += 1
            assert len(collection['packages']) == numfiles
            for pkg in collection['packages']:
                assert pkg['arch'] in update.filelist.keys()
                found = False
                for file in update.filelist[pkg['arch']]:
                    if pkg['filename'] in file:
                        found = True
                        break
                assert found

        # TODO: generate metadata! and verify (repoquery ?)

        print "Moving update"
        update.request = 'move'
        print "Pushing to temp stage: %s" % push_stage
        for msg in update.run_request(stage=push_stage):
            pass

        # o check both updateinfo.xml.gz
        # o make sure old files are gone and new ones exist
        # o Try another update with broken upgrade paths

        print "Push stage = ", push_stage
        #assert False

        shutil.rmtree(push_stage)

    def test_email(self):
        from bodhi import mail
        update = self.get_update(name='mutt-1.5.14-1.fc7')
        bug = self.get_bug()
        cve = self.get_cve()
        update.addBugzilla(bug)
        update.addCVE(cve)
        update.assign_id()
        template = mail.get_template(update)
        # TODO: assert template against known correct template
        #assert False

    def test_no_srpm(self):
        from bodhi.exceptions import RPMNotFound
        try:
            update = self.get_update(name='foobar-1.2-3')
        except RPMNotFound:
            pass
        except Exception:
            assert False

class TestCVE(testutil.DBTest):

    def get_model(self):
        return CVE

    def test_creation(self):
        cve = CVE(cve_id="CVE-2006-0000")

class TestBugzilla(testutil.DBTest):

    def get_model(self):
        return Bugzilla

    def test_creation(self):
        bug = Bugzilla(bz_id=1)
        # TODO: make sure title was fetched properly, and 
        # any security flags
