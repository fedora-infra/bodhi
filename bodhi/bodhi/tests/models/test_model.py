# -*- coding: utf-8 -*-
"""Test suite for the Bodhi models"""

import os
import time

from tg import config
from nose.tools import eq_
from datetime import datetime

from bodhi import model
from bodhi.tests.models import ModelTest

class TestRelease(ModelTest):
    """Unit test case for the ``Release`` model."""
    klass = model.Release
    attrs = dict(
        name = u"F11",
        long_name = u"Fedora 11",
        id_prefix = u"FEDORA",
        dist_tag = u"dist-f11",
        candidate_tag = u"dist-f11-updates-candidate",
        testing_tag = u"dist-f11-updates-testing",
        stable_tag = u"dist-f11-updates",
        version = 11,
        locked = False,
        metrics = {'test_metric': [0, 1, 2, 3, 4]}
        )


class TestEPELRelease(ModelTest):
    """Unit test case for the ``Release`` model."""
    klass = model.Release
    attrs = dict(
        name = u"EL5",
        long_name = u"Fedora EPEL 5",
        id_prefix = u"FEDORA-EPEL",
        dist_tag = u"dist-5E-epel",
        candidate_tag = u"dist-5E-epel-testing-candidate",
        testing_tag = u"dist-5E-epel-testing",
        stable_tag = u"dist-5E-epel",
        version = 5,
        )


class TestPackage(ModelTest):
    """Unit test case for the ``Package`` model."""
    klass = model.Package
    attrs = dict(
        name = u"TurboGears",
        committers = ['lmacken'],
        stable_karma = 5,
        unstable_karma = -3,
        )


class TestBuild(ModelTest):
    """Unit test case for the ``Build`` model."""
    klass = model.Build
    attrs = dict(
        nvr = u"TurboGears-1.0.8-3.fc11",
        inherited = False,
        )

    def do_get_dependencies(self):
        return dict(
                release = model.Release(**TestRelease.attrs),
                package = model.Package(**TestPackage.attrs),
                )

    def test_release_relation(self):
        eq_(self.obj.release.name, u"F11")
        eq_(len(self.obj.release.builds), 1)
        eq_(self.obj.release.builds[0], self.obj)

    def test_package_relation(self):
        eq_(self.obj.package.name, u"TurboGears")
        eq_(len(self.obj.package.builds), 1)
        eq_(self.obj.package.builds[0], self.obj)

    def test_latest(self):
        # Note, this build is hardcoded in bodhi/buildsys.py:DevBuildsys
        eq_(self.obj.get_latest(), u"TurboGears-1.0.8-7.fc11")

    def test_latest_with_eq_build(self):
        self.obj.nvr = 'TurboGears-1.0.8-7.fc11'
        eq_(self.obj.get_latest(), None)

    def test_latest_with_newer_build(self):
        self.obj.nvr = 'TurboGears-1.0.8-8.fc11'
        eq_(self.obj.get_latest(), None)

    def test_latest_srpm(self):
        eq_(self.obj.get_latest_srpm(), os.path.join(config.get('build_dir'),
            'TurboGears/1.0.8/7.fc11/src/TurboGears-1.0.8-7.fc11.src.rpm'))

    def test_url(self):
        eq_(self.obj.get_url(), '/TurboGears-1.0.8-3.fc11')


class TestUpdate(ModelTest):
    """Unit test case for the ``Update`` model."""
    klass = model.Update
    attrs = dict(
        type_=u'security',
        notes=u'foobar',
        status=u'pending',
        submitter=u'lmacken',
        request=u'testing',
        close_bugs=True,
        karma=0,
        )

    def do_get_dependencies(self):
        release = model.Release(**TestRelease.attrs)
        return dict(
            builds = [model.Build(nvr=u'TurboGears-1.0.8-3.fc11',
                            package=model.Package(**TestPackage.attrs),
                            release = release)],
            bugs = [model.Bug(bug_id=1), model.Bug(bug_id=2)],
            cves = [model.CVE(cve_id=u'CVE-2009-0001')],
            release = release,
            )

    def get_update(self, name=u'TurboGears-1.0.8-3.fc11'):
        attrs = self.attrs.copy()
        pkg = model.DBSession.query(model.Package).filter_by(name=u'TurboGears').one()
        rel = model.DBSession.query(model.Release).filter_by(name=u'F11').one()
        attrs.update(dict(
            builds = [model.Build(nvr=name, package=pkg, release=rel)],
            release = rel,
            ))
        return self.klass(**attrs)

    def test_builds(self):
        eq_(len(self.obj.builds), 1)
        eq_(self.obj.builds[0].nvr, u'TurboGears-1.0.8-3.fc11')
        eq_(self.obj.builds[0].release.name, u'F11')
        eq_(self.obj.builds[0].package.name, u'TurboGears')

    def test_title(self):
        eq_(self.obj.title, u'TurboGears security update')

    def test_pkg_str(self):
        """ Ensure str(pkg) is correct """
        eq_(str(self.obj.builds[0].package), '================================================================================\n     TurboGears\n================================================================================\n\n Pending Updates (1)\n    o TurboGears-1.0.8-3.fc11\n')

    def test_bugstring(self):
        eq_(self.obj.get_bugstring(), u'1 2')

    def test_cvestring(self):
        eq_(self.obj.get_cvestring(), u'CVE-2009-0001')

    def test_assign_id(self):
        update = self.obj
        update.assign_id()
        eq_(update.alias, u'%s-%s-0001' % (update.release.id_prefix,
                                          time.localtime()[0]))
        #assert update.date_pushed

        update = self.get_update(name=u'TurboGears-0.4.4-8.fc11')
        update.assign_id()
        eq_(update.alias, u'%s-%s-0002' % (update.release.id_prefix,
                                          time.localtime()[0]))

        ## Create another update for another release that has the same
        ## Release.id_prefix.  This used to trigger a bug that would cause
        ## duplicate IDs across Fedora 10/11 updates.
        update = self.get_update(name=u'nethack-3.4.5-1.fc10')
        otherrel = model.Release(name=u'fc10', long_name=u'Fedora 10',
                                 id_prefix=u'FEDORA', dist_tag=u'dist-fc10')
        update.release = otherrel
        update.assign_id()
        eq_(update.alias, u'%s-%s-0003' % (update.release.id_prefix,
                                          time.localtime()[0]))

        ## 10k bug
        update.alias = u'FEDORA-2009-9999'
        newupdate = self.get_update(name=u'nethack-2.5.6-1.fc10')
        newupdate.assign_id()
        eq_(newupdate.alias, u'FEDORA-2009-10000')

        newerupdate = self.get_update(name=u'nethack-2.5.7-1.fc10')
        newerupdate.assign_id()
        eq_(newerupdate.alias, u'FEDORA-2009-10001')

        ## test updates that were pushed at the same time.  assign_id should
        ## be able to figure out which one has the highest id.
        now = datetime.utcnow()
        newupdate.date_pushed = now
        newerupdate.date_pushed = now

        newest = self.get_update(name=u'nethack-2.5.8-1.fc10')
        newest.assign_id()
        eq_(newest.alias, u'FEDORA-2009-10002')

# test multibuild update
