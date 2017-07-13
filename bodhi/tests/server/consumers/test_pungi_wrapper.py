# -*- coding: utf-8 -*-
# Copyright © 2017 Red Hat, Inc.
#
# This file is part of Bodhi.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import mock
import os

from pungi.compose import Compose
import pytest

from bodhi.server.consumers.pungi_wrapper import (
    PungiWrapper, PungiConfig, VariantsConfig
)


@pytest.mark.usefixture("get_pungi_conf")
@pytest.fixture(scope="module")
def get_compose(pungi_conf, compose_dir):

    logger = mock.Mock()

    compose = Compose(pungi_conf, topdir=compose_dir, debug=True, skip_phases=["productimg"],
                      just_phases=[], old_composes=None, koji_event=None, supported=False,
                      logger=logger, notifier=mock.Mock())

    return compose


@pytest.fixture(scope="module")
def get_pungi_conf(tmpdir, config_str=None):
    conf = tmpdir.mkdir("conf").join("pungi.conf")
    config_data = """ # RELEASE
    release_name = "Fedora"
    release_short = "Fedora"
    release_version = "23"

    # GENERAL SETTINGS
    comps_file = "comps-f23.xml"
    variants_file = "variants-f23.xml"

    # KOJI
    koji_profile = "koji"
    runroot = False

    # PKGSET
    sigkeys = [None]
    pkgset_source = "koji"
    pkgset_koji_tag = "f23"

    # CREATEREPO
    createrepo_checksum = "sha256"

    # GATHER
    gather_source = "comps"
    gather_method = "deps"
    greedy_method = "build"
    check_deps = False

    # BUILDINSTALL
    bootable = True
    buildinstall_method = "lorax"
    release_is_layered = True

    base_product_name = "Fedora"
    base_product_short = "Fedora"
    base_product_version = "23" """
    if config_str:
        config_data = config_str
    conf.write(config_data)

    return conf


@pytest.mark.usefixture("get_pungi_conf")
class TestPungiConfig(object):

    def test_load_config_from_file(self, tmpdir):
        logger = mock.Mock()
        pungi_conf = get_pungi_conf(tmpdir)

        conf_xml = PungiConfig(path=str(pungi_conf), logger=logger)
        assert isinstance(conf_xml, dict)
        assert isinstance(conf_xml["sigkeys"], list)
        assert conf_xml["release_name"] == "Fedora"
        assert conf_xml["release_version"] == "23"

    def test_valid_pungi_config(self, tmpdir):
        logger = mock.Mock()
        config_data = """ # RELEASE
        release_name = "Fedora"
        release_short = "Fedora"
        release_version = "23" """
        pungi_conf = get_pungi_conf(tmpdir, config_data)

        with pytest.raises(Exception):
            PungiConfig(path=str(pungi_conf), logger=logger)


@pytest.fixture(scope="module")
def get_updates_and_builds():
    updates = [u'host-master-20170830200108', u'platform-master-20170818100407']
    builds = [
        u'platform-master-20160818100407',
        u'platform-master-20160818100408',
        u'shim-master-20160502110605',
        u'shim-master-20160502110601',
        u'host-master-20170830200108',
        u'host-master-20170830200109',
        u'installer-master-20170822180922',
        u'installer-master-20170822180920'
    ]
    mock_updates = []
    mock_builds = []
    for update in updates:
        mock_update = mock.Mock()
        mock_update.title = update
        mock_updates.append(mock_update)

    for build in builds:
        mock_build = mock.Mock()
        mock_build.nvr = build
        mock_builds.append(mock_build)

    return mock_updates, mock_builds


@pytest.mark.usefixture("get_updates_and_builds")
class TestVariantsConfig(object):

    def test_generate_module_list(self):
        updates, builds = get_updates_and_builds()
        variants_conf = VariantsConfig(updates, builds)

        module_list = variants_conf._generate_module_list()
        assert isinstance(module_list, list)
        assert len(module_list) == 4

    def test_create_an_updated_variants_conf(self):
        updates, builds = get_updates_and_builds()
        variants_conf = VariantsConfig(updates, builds)

        assert isinstance(variants_conf, VariantsConfig)
        assert isinstance(variants_conf.xml, str)
        assert 'id="Server"' in variants_conf.xml
        assert '<module>host-master-20170830200108</module>' in variants_conf.xml
        assert '<module>platform-master-20170818100407</module>' in variants_conf.xml
        assert '<module>shim-master-20160502110605</module>' in variants_conf.xml
        assert '<module>installer-master-20170822180922</module>' in variants_conf.xml


@pytest.mark.usefixture("get_compose")
@pytest.mark.usefixture("get_updates_and_builds")
class TestPungiWrapper(object):

    """ This set of tests test the wrapper created around pungi for the masher. """

    @staticmethod
    def _test_phase_start_stop(phase_instance):
        return phase_instance.start.assert_called_once() and \
            phase_instance.stop.assert_called_once()

    @mock.patch("pungi.metadata")
    @mock.patch("bodhi.server.consumers.pungi_wrapper.PungiWrapper.write_repo_metadata")
    @mock.patch("bodhi.server.consumers.pungi_wrapper.PungiWrapper.create_latest_repo_links")
    @mock.patch("pungi.phases")
    def test_execute_phases(self, pungi_phases, create_latest_repo_links,
                            write_repo_metadata, pungi_metadata):
        compose = mock.Mock()
        variants_conf = mock.Mock()

        wrapper = PungiWrapper(compose, variants_conf)

        wrapper.execute_phases()

        phases = [
            {"pkgset": False, "class": pungi_phases.InitPhase},
            {"pkgset": False, "class": pungi_phases.PkgsetPhase},
            {"pkgset": False, "class": pungi_phases.BuildinstallPhase},
            {"pkgset": True, "class": pungi_phases.GatherPhase},
            {"pkgset": True, "class": pungi_phases.ExtraFilesPhase},
            {"pkgset": False, "class": pungi_phases.CreaterepoPhase},
            {"pkgset": False, "class": pungi_phases.OstreeInstallerPhase},
            {"pkgset": False, "class": pungi_phases.OSTreePhase},
            {"pkgset": True, "class": pungi_phases.ProductimgPhase},
            {"pkgset": False, "class": pungi_phases.CreateisoPhase},
            {"pkgset": False, "class": pungi_phases.LiveImagesPhase},
            {"pkgset": False, "class": pungi_phases.LiveMediaPhase},
            {"pkgset": False, "class": pungi_phases.ImageBuildPhase},
            {"pkgset": False, "class": pungi_phases.OSBSPhase},
            {"pkgset": False, "class": pungi_phases.ImageChecksumPhase},
            {"pkgset": False, "class": pungi_phases.TestPhase}
        ]
        phases_start_stop = [
            pungi_phases.InitPhase,
            pungi_phases.PkgsetPhase,
            pungi_phases.BuildinstallPhase,
            pungi_phases.GatherPhase,
            pungi_phases.ExtraFilesPhase,
            pungi_phases.CreaterepoPhase,
            pungi_phases.OSTreePhase,
            pungi_phases.ProductimgPhase,
            pungi_phases.ImageChecksumPhase,
            pungi_phases.TestPhase
        ]
        for phase in phases:
            if phase["pkgset"]:
                phase["class"].assert_called_once_with(compose, pungi_phases.PkgsetPhase())
            else:
                phase["class"].assert_called_once_with(compose)

        for phase in phases_start_stop:
            phase_instance = phase()
            self._test_phase_start_stop(phase_instance)

        pungi_phases.run_all.assert_called_once()
        args, kwargs = pungi_phases.run_all.call_args
        assert len(args[0]) == 6
        create_latest_repo_links.assert_called_once()
        write_repo_metadata.assert_called_once()

    @mock.patch("pungi.metadata")
    @mock.patch("bodhi.server.consumers.pungi_wrapper.PungiWrapper.write_repo_metadata")
    @mock.patch("bodhi.server.consumers.pungi_wrapper.PungiWrapper.create_latest_repo_links")
    @mock.patch("pungi.phases")
    def test_execute_phases_validate(self, pungi_phases, *args):
        compose = mock.Mock()
        variants_conf = mock.Mock()
        phases = [
            {"pkgset": False, "class": pungi_phases.InitPhase},
            {"pkgset": False, "class": pungi_phases.PkgsetPhase},
            {"pkgset": False, "class": pungi_phases.BuildinstallPhase},
            {"pkgset": True, "class": pungi_phases.GatherPhase},
            {"pkgset": True, "class": pungi_phases.ExtraFilesPhase},
            {"pkgset": False, "class": pungi_phases.CreaterepoPhase},
            {"pkgset": False, "class": pungi_phases.OstreeInstallerPhase},
            {"pkgset": False, "class": pungi_phases.OSTreePhase},
            {"pkgset": True, "class": pungi_phases.ProductimgPhase},
            {"pkgset": False, "class": pungi_phases.CreateisoPhase},
            {"pkgset": False, "class": pungi_phases.LiveImagesPhase},
            {"pkgset": False, "class": pungi_phases.LiveMediaPhase},
            {"pkgset": False, "class": pungi_phases.ImageBuildPhase},
            {"pkgset": False, "class": pungi_phases.OSBSPhase},
            {"pkgset": False, "class": pungi_phases.ImageChecksumPhase},
            {"pkgset": False, "class": pungi_phases.TestPhase}
        ]
        for phase in phases:
            phase_instance = phase["class"]()
            phase_instance.skip.return_value = False

        wrapper = PungiWrapper(compose, variants_conf)

        wrapper.execute_phases()

        for phase in phases:
            phase_instance = phase["class"]()
            phase_instance.validate.assert_called_once()

    @mock.patch("pungi.metadata")
    @mock.patch("bodhi.server.consumers.pungi_wrapper.PungiWrapper.write_repo_metadata")
    @mock.patch("bodhi.server.consumers.pungi_wrapper.PungiWrapper.create_latest_repo_links")
    @mock.patch("pungi.phases")
    def test_execute_phases_exception(self, pungi_phases, *args):
        init_phase = pungi_phases.InitPhase()
        init_phase.validate.side_effect = ValueError("Test Error")
        init_phase.skip.return_value = False
        init_phase.name = "init phase"
        compose = mock.Mock()
        variants_conf = mock.Mock()
        wrapper = PungiWrapper(compose, variants_conf)

        with pytest.raises(Exception):
            wrapper.execute_phases()

    @mock.patch("pungi.util")
    def test_init_compose_dir(self, util, tmpdir):
        compose = mock.Mock()
        variants_conf = mock.Mock()
        logger = mock.Mock()
        wrapper = PungiWrapper(compose, variants_conf)

        topdir = str(tmpdir.mkdir("mash-dir"))
        pungi_conf_path = get_pungi_conf(tmpdir)
        pungi_conf = PungiConfig(str(pungi_conf_path), logger)
        compose_id = "f27-modular-updates"
        compose_dir = wrapper.init_compose_dir(topdir, pungi_conf, compose_id)

        assert compose_dir == os.path.join(topdir, compose_id)

    @mock.patch("bodhi.server.consumers.pungi_wrapper.PungiWrapper.load_variants_config")
    @mock.patch("bodhi.server.consumers.pungi_wrapper.PungiWrapper.execute_phases")
    def test_compose_repo(self, load_variants_config, execute_phases):
        compose = mock.Mock()
        variants_conf = mock.Mock()

        wrapper = PungiWrapper(compose, variants_conf)

        wrapper.compose_repo()

        load_variants_config.assert_called_once_with()
        execute_phases.assert_called_once_with()

    @mock.patch("shutil.copyfileobj")
    def test_load_variants_config(self, copyfileobj, tmpdir):
        logger = mock.Mock()
        topdir = str(tmpdir.mkdir("mash_dir"))
        compose_id = "f27-modular-updates"
        pungi_conf_path = get_pungi_conf(tmpdir)
        pungi_conf = PungiConfig(str(pungi_conf_path), logger)
        compose_dir = PungiWrapper.init_compose_dir(topdir, pungi_conf, compose_id)

        compose = get_compose(pungi_conf, compose_dir)
        updates, builds = get_updates_and_builds()
        variants_conf = VariantsConfig(updates, builds)
        topdir = compose.topdir

        wrapper = PungiWrapper(compose, variants_conf)
        wrapper.load_variants_config()

        assert len(wrapper.compose.all_variants)
        copyfileobj.assert_called_once()

    @mock.patch("pungi.metadata")
    def test_write_repo_metadata(self, pungi_metadata, tmpdir):
        logger = mock.Mock()
        topdir = str(tmpdir.mkdir("mash_dir"))
        compose_id = "f27-modular-updates"
        pungi_conf_path = get_pungi_conf(tmpdir)
        pungi_conf = PungiConfig(str(pungi_conf_path), logger)
        compose_dir = PungiWrapper.init_compose_dir(topdir, pungi_conf, compose_id)

        compose = get_compose(pungi_conf, compose_dir)
        updates, builds = get_updates_and_builds()
        variants_conf = VariantsConfig(updates, builds)
        topdir = compose.topdir

        wrapper = PungiWrapper(compose, variants_conf)
        wrapper.load_variants_config()
        wrapper.write_repo_metadata()
        assert pungi_metadata.write_tree_info.call_count == 8
        assert pungi_metadata.write_discinfo.call_count == 8
        assert pungi_metadata.write_media_repo.call_count == 8

    @mock.patch("os.symlink")
    @mock.patch("os.unlink")
    def test_create_latest_symlinks(self, unlink, symlink, tmpdir):
        logger = mock.Mock()
        topdir = str(tmpdir.mkdir("mash_dir"))
        compose_id = "f27-modular-updates"
        pungi_conf_path = get_pungi_conf(tmpdir)
        pungi_conf = PungiConfig(str(pungi_conf_path), logger)
        compose_dir = PungiWrapper.init_compose_dir(topdir, pungi_conf, compose_id)

        compose = get_compose(pungi_conf, compose_dir)
        updates, builds = get_updates_and_builds()
        variants_conf = VariantsConfig(updates, builds)
        topdir = compose.topdir

        wrapper = PungiWrapper(compose, variants_conf)
        wrapper.create_latest_repo_links()
        unlink.assert_called_once()
        symlink.assert_called_once()

    @mock.patch("os.symlink")
    @mock.patch("os.unlink")
    def test_create_latest_symlinks_unlink_exception(self, unlink, symlink, tmpdir):
        logger = mock.Mock()
        topdir = str(tmpdir.mkdir("mash_dir"))
        compose_id = "f27-modular-updates"
        pungi_conf_path = get_pungi_conf(tmpdir)
        pungi_conf = PungiConfig(str(pungi_conf_path), logger)
        compose_dir = PungiWrapper.init_compose_dir(topdir, pungi_conf, compose_id)

        compose = get_compose(pungi_conf, compose_dir)
        updates, builds = get_updates_and_builds()
        variants_conf = VariantsConfig(updates, builds)
        topdir = compose.topdir

        wrapper = PungiWrapper(compose, variants_conf)

        with pytest.raises(Exception):
            ex = OSError("Test error")
            ex.errno = 1
            unlink.side_effect = ex
            wrapper.create_latest_repo_links()

    @mock.patch("os.symlink")
    @mock.patch("os.unlink")
    def test_create_latest_symlinks_symlink_exception(self, unlink, symlink, tmpdir):
        logger = mock.Mock()
        topdir = str(tmpdir.mkdir("mash_dir"))
        compose_id = "f27-modular-updates"
        pungi_conf_path = get_pungi_conf(tmpdir)
        pungi_conf = PungiConfig(str(pungi_conf_path), logger)
        compose_dir = PungiWrapper.init_compose_dir(topdir, pungi_conf, compose_id)

        compose = get_compose(pungi_conf, compose_dir)
        updates, builds = get_updates_and_builds()
        variants_conf = VariantsConfig(updates, builds)
        topdir = compose.topdir

        wrapper = PungiWrapper(compose, variants_conf)

        ex = Exception("Test error")
        ex.errno = 1
        symlink.side_effect = ex
        compose.log_error = mock.Mock()
        wrapper.create_latest_repo_links()
        compose.log_error.assert_called_once()
