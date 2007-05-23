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

    def _verify_updateinfo(self, update, repo):
        """ Verify that the updateinfo.xml.gz for a given repo matches the
            data for a given update
        """
        print "_verify_updateinfo(%s, %s)" % (update.nvr, repo)
        uinfo = UpdateMetadata()
        uinfo.add(repo)
        notice = uinfo.get_notice(update.nvr)
        assert notice
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

        # Generate repo metadata
        from bodhi.push import generate_metadata
        for x in generate_metadata(update.release, update.testing,
                                   stage=push_stage): pass

        # Verify the updateinfo.xml.gz
        for arch in update.filelist.keys():
            self._verify_updateinfo(update, join(repo, arch, 'repodata',
                                                 'updateinfo.xml.gz'))

        # Move update from Testing to Final
        update.request = 'move'
        print "Pushing to temp stage: %s" % push_stage
        for msg in update.run_request(stage=push_stage): pass

        # Generate repo metadata
        from bodhi.push import generate_metadata
        for x in generate_metadata(update.release, update.testing,
                                   stage=push_stage): pass

        # Make sure we're in a different repo now
        newrepo = join(push_stage, update.get_repo())
        assert newrepo != repo

        # Verify the updateinfo.xml.gz
        for arch in update.filelist.keys():
            self._verify_updateinfo(update, join(newrepo, arch, 'repodata',
                                                 'updateinfo.xml.gz'))

        # Make sure this update has been removed from the old updateinfo
        for arch in update.filelist.keys():
            uinfo = UpdateMetadata()
            uinfo.add(join(repo, arch, 'repodata', 'updateinfo.xml.gz'))
            notice = uinfo.get_notice(update.nvr)
            assert notice == None

        # Make sure files exist at new location
        self._assert_files(update, newrepo)

        # Make sure files don't exist at old location
        try:
            self._assert_files(update, repo)
        except AssertionError:
            # At this point, everything should be kosher
            shutil.rmtree(push_stage)
            return

        assert False

    def test_email(self):
        from bodhi import mail
        update = self.get_update(name='mutt-1.5.14-1.fc7')
        bug = self.get_bug()
        cve = self.get_cve()
        update.addBugzilla(bug)
        update.addCVE(cve)
        update.assign_id()
        template = mail.get_template(update)
        assert template
        assert template == u"\nSubject: [SECURITY] Fedora 7 Test Update: mutt-1.5.14-1.fc7\n\n--------------------------------------------------------------------------------\nFedora Test Update Notification\nFEDORA-2007-0001\nNone\n--------------------------------------------------------------------------------\n\nName        : mutt\nProduct     : Fedora 7\nVersion     : 1.5.14\nRelease     : 1.fc7\nSummary     : A text mode mail user agent\nDescription :\nMutt is a text-mode mail user agent. Mutt supports color, threading,\narbitrary key remapping, and a lot of customization.\n\nYou should install mutt if you have used it in the past and you prefer\nit, or if you are new to mail programs and have not decided which one\nyou are going to use.\n\n--------------------------------------------------------------------------------\nUpdate Information:\n\nfoobar\n--------------------------------------------------------------------------------\nReferences:\n\n  Bug #1 - https://bugzilla.redhat.com/bugzilla/show_bug.cgi?id=1\n  CVE-2007-0000 - http://www.cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2007-0000\n--------------------------------------------------------------------------------\n\nThis update can be downloaded from:\n    http://download.fedoraproject.org/pub/fedora/linux/core/updates/testing/7/\n\nf31e57d24a37a4616c397df221515f1f18d7cc58  ppc/mutt-1.5.14-1.fc7.ppc.rpm\n423bd720bb3c1b095bd67311046a62ccaadfcbc1  ppc/debug/mutt-debuginfo-1.5.14-1.fc7.ppc.rpm\nae07587736a31b7b666e4b09f47ebb7cc842bc8c  x86_64/mutt-1.5.14-1.fc7.x86_64.rpm\n22fa9519ad3a13710ce62b9983e0fe3dde6a9473  x86_64/debug/mutt-debuginfo-1.5.14-1.fc7.x86_64.rpm\n71140a390ab41e62e14fe1939b243afacb7369bf  i386/mutt-1.5.14-1.fc7.i386.rpm\n60e794cb7f99ce640bda6649ec4adc4e9b4f89c0  i386/debug/mutt-debuginfo-1.5.14-1.fc7.i386.rpm\nfe0820de7c5e10b1df28221f3b946892c27800f1  SRPMS/mutt-1.5.14-1.fc7.src.rpm\n\nThis update can be installed with the 'yum' update program.  Use 'yum update\npackage-name' at the command line.  For more information, refer to 'Managing\nSoftware with yum,' available at http://docs.fedoraproject.org/yum/.\n--------------------------------------------------------------------------------\n"


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
