# -*- coding: utf-8 -*-
"""Test suite for the Bodhi models"""
import os

from tg import config
from nose.tools import eq_

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
    klass = model.Build
    attrs = dict(
        title = u"TurboGears-1.0.8-3.fc11",
        )

    def do_get_dependencies(self):
        return dict(
                release = model.Release(**TestRelease.attrs),
                package = model.Package(**TestPackage.attrs),
                )
