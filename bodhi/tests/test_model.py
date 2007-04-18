# $Id: test_model.py,v 1.5 2006/12/31 09:10:25 lmacken Exp $

import os
import sys
import time
import shutil
import tempfile
import turbogears

from os.path import join, exists
from turbogears import testutil, database, config
from bodhi.util import mkmetadatadir
from bodhi.model import (Release, Package, PackageUpdate, Bugzilla,
                         Comment, CVE, Arch)

database.set_db_uri("sqlite:///:memory:")
turbogears.update_config(configfile='dev.cfg',
                         modulename='bodhi.config')

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
        rel = Release(name='fc7', long_name='Fedora 7', repodir='7')
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

    def test_push(self):
        push_stage = tempfile.mkdtemp('bodhi')
        update = self.get_update()
        for arch in update.release.arches:
            mkmetadatadir(join(push_stage, update.get_repo(), arch.name))
            mkmetadatadir(join(push_stage, update.get_repo(),arch.name,'debug'))
        mkmetadatadir(join(push_stage, update.get_repo(), 'SRPMS'))
        update.request = 'push'
        print "Pushing to temp stage: %s" % push_stage
        for msg in update.run_request(stage=push_stage): pass
        for arch in update.release.arches:
            assert exists(join(push_stage, update.get_repo(), arch.name,
                               "%s.%s.rpm" % (update.nvr, arch.name)))
            assert exists(join(push_stage, update.get_repo(), arch.name,
                               'debug', "mutt-debuginfo-1.5.14-1.fc7.%s.rpm" %
                               arch.name))
        assert exists(join(push_stage, update.get_repo(), 'SRPMS',
                           "%s.src.rpm" % update.nvr))
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
        # TODO: assert template against known correct templaet
        #assert False

    def test_no_srpm(self):
        from bodhi.exceptions import SRPMNotFound
        try:
            update = self.get_update(name='foobar-1.2-3')
        except SRPMNotFound:
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
