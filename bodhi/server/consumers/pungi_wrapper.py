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
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""
Our Very Own Pungi Wrapper.

This module comprises tools that wrap pungi providing a kind of "API" we use
internally.  Once pungi gets its own proper API, this module will either need
to be refactored or abandoned.
"""

import errno
import os
import time
import cStringIO
import shutil

import pungi.checks
import pungi.phases
import pungi.metadata
import pungi.notifier
import kobo.conf
from bodhi.server import log
from productmd.composeinfo import ComposeInfo
from pungi.wrappers.variants import VariantsXmlParser
from pungi.util import makedirs

from bodhi.server.config import _validate_bool as asbool


class PungiWrapper(object):
    """Pungi Wrapper which wraps the pungi package functionality."""

    def __init__(self, compose, variants_conf):
        self.phases = {}
        self.compose = compose
        self.variants_conf = variants_conf

    @staticmethod
    def init_compose_dir(topdir, conf, compose_id, compose_type="production"):
        """
        Pungi method which needed to be changed to work with bodhi. Creates
        necessary directories and files for the compose to be succesfull

        Args:
            topdir (str) - mash dir
            conf (dict) - pungi conf
            compose_id (str) - compose id
            compose_type (str) - type of the compose
        Returns:
            str: Path to the compose_dir
        """
        compose_date = None
        compose_respin = None
        compose_label = None
        already_exists_callbacks = None

        already_exists_callbacks = already_exists_callbacks or []

        # create an incomplete composeinfo to generate compose ID
        ci = ComposeInfo()
        ci.release.name = conf["release_name"]
        ci.release.short = conf["release_short"]
        ci.release.version = conf["release_version"]
        ci.release.is_layered = asbool(conf.get("release_is_layered", False))
        ci.release.type = conf.get("release_type", "ga").lower()
        ci.release.internal = asbool(conf.get("release_internal", False))
        if ci.release.is_layered:
            ci.base_product.name = conf["base_product_name"]
            ci.base_product.short = conf["base_product_short"]
            ci.base_product.version = conf["base_product_version"]
            ci.base_product.type = conf.get("base_product_type", "ga").lower()

        ci.compose.label = compose_label
        ci.compose.type = compose_type
        ci.compose.date = compose_date or time.strftime("%Y%m%d", time.gmtime())
        ci.compose.respin = compose_respin or 0

        ci.compose.id = ci.create_compose_id()

        compose_dir = os.path.join(topdir, compose_id)

        os.makedirs(compose_dir)

        with open(os.path.join(compose_dir, "COMPOSE_ID"), "w") as fd:
            fd.write(ci.compose.id)
        work_dir = os.path.join(compose_dir, "work", "global")
        makedirs(work_dir)
        ci.dump(os.path.join(work_dir, "composeinfo-base.json"))
        return compose_dir

    def compose_repo(self):
        """
        Wrapper method which start the compose process with loading the variants
        config and executing all the phases necessary for a pungi compose
        """
        self.load_variants_config()
        self.execute_phases()

    def execute_phases(self):
        """
        This method is inspired by the pungi-koji binary. It composes a dnf repo
        according to the compose object provided.
        """
        init_phase = pungi.phases.InitPhase(self.compose)
        pkgset_phase = pungi.phases.PkgsetPhase(self.compose)
        buildinstall_phase = pungi.phases.BuildinstallPhase(self.compose)
        gather_phase = pungi.phases.GatherPhase(self.compose, pkgset_phase)
        extrafiles_phase = pungi.phases.ExtraFilesPhase(self.compose, pkgset_phase)
        createrepo_phase = pungi.phases.CreaterepoPhase(self.compose)
        ostree_installer_phase = pungi.phases.OstreeInstallerPhase(self.compose)
        ostree_phase = pungi.phases.OSTreePhase(self.compose)
        productimg_phase = pungi.phases.ProductimgPhase(self.compose, pkgset_phase)
        createiso_phase = pungi.phases.CreateisoPhase(self.compose)
        liveimages_phase = pungi.phases.LiveImagesPhase(self.compose)
        livemedia_phase = pungi.phases.LiveMediaPhase(self.compose)
        image_build_phase = pungi.phases.ImageBuildPhase(self.compose)
        osbs_phase = pungi.phases.OSBSPhase(self.compose)
        image_checksum_phase = pungi.phases.ImageChecksumPhase(self.compose)
        test_phase = pungi.phases.TestPhase(self.compose)

        errors = []
        # check if all config options are set
        for phase in (init_phase, pkgset_phase, createrepo_phase,
                      buildinstall_phase, productimg_phase, gather_phase,
                      extrafiles_phase, createiso_phase, liveimages_phase,
                      livemedia_phase, image_build_phase, image_checksum_phase,
                      test_phase, ostree_phase, ostree_installer_phase,
                      osbs_phase):
            if phase.skip():
                continue
            try:
                phase.validate()
            except ValueError as ex:
                for i in str(ex).splitlines():
                    errors.append("%s: %s" % (phase.name.upper(), i))
        if errors:
            for i in errors:
                self.compose.log_error(i)
            raise RuntimeError(errors)

        # INIT phase
        init_phase.start()
        init_phase.stop()

        # PKGSET phase
        pkgset_phase.start()
        pkgset_phase.stop()

        # BUILDINSTALL phase - start, we can run gathering, extra files and
        # createrepo while buildinstall is in progress.
        buildinstall_phase.start()

        # If any of the following three phases fail, we must ensure that
        # buildinstall is stopped. Otherwise the whole process will hang.
        try:
            gather_phase.start()
            gather_phase.stop()

            extrafiles_phase.start()
            extrafiles_phase.stop()

            createrepo_phase.start()
            createrepo_phase.stop()

        finally:
            buildinstall_phase.stop()

        if not buildinstall_phase.skip():
            buildinstall_phase.copy_files()

        ostree_phase.start()
        ostree_phase.stop()

        # PRODUCTIMG phase
        productimg_phase.start()
        productimg_phase.stop()

        self.write_repo_metadata()

        # Start all phases for image artifacts
        pungi.phases.run_all([createiso_phase, liveimages_phase,
                              image_build_phase, livemedia_phase,
                              ostree_installer_phase, osbs_phase])

        image_checksum_phase.start()
        image_checksum_phase.stop()

        pungi.metadata.write_compose_info(self.compose)
        self.compose.im.dump(self.compose.paths.compose.metadata("images.json"))

        osbs_phase.dump_metadata()

        # TEST phase
        test_phase.start()
        test_phase.stop()

        self.compose.write_status("FINISHED")

        self.create_latest_repo_links()

        self.compose.log_info("Compose finished: %s" % self.compose.topdir)

    def load_variants_config(self):
        """
        This is a workaround so we dont have to provide a path of the variants
        config to pungi. We provide a generated file object which then is injected
        into pungi compose object.
        """
        variants_file_obj = cStringIO.StringIO(self.variants_conf.xml)
        parser = VariantsXmlParser(variants_file_obj)
        self.compose.variants = parser.parse()
        self.compose.all_variants = {}
        for variant in self.compose.get_variants():
            self.compose.all_variants[variant.uid] = variant
        # After the variants object is injected into the pungi compose object
        # we will write it to disk in the repo.
        variants_file = self.compose.paths.work.variants_file(arch="global")
        variants_file_obj.seek(0)
        # Create create the variants file on disk
        with open(variants_file, 'w') as fd:
            shutil.copyfileobj(variants_file_obj, fd)
            variants_file_obj.close()

    def write_repo_metadata(self):
        # write treeinfo before ISOs are created
        for variant in self.compose.get_variants():
            for arch in variant.arches + ["src"]:
                pungi.metadata.write_tree_info(self.compose, arch, variant)

        # write .discinfo and media.repo before ISOs are created
        for variant in self.compose.get_variants():
            for arch in variant.arches + ["src"]:
                timestamp = pungi.metadata.write_discinfo(self.compose, arch, variant)
                pungi.metadata.write_media_repo(self.compose, arch, variant, timestamp)

    def create_latest_repo_links(self):
        """
        Creates symlinks for the newly created compose
        """
        self.compose_dir = os.path.basename(self.compose.topdir)
        symlink_name = "latest-%s-%s" % (
            self.compose.conf["release_short"],
            self.compose.conf["release_version"]
        )
        if self.compose.conf["release_is_layered"]:
            symlink_name += "-%s-%s" % (
                self.compose.conf["base_product_short"],
                self.compose.conf["base_product_version"]
            )
        symlink = os.path.join(self.compose.topdir, "..", symlink_name)

        try:
            os.unlink(symlink)
        except OSError as ex:
            if ex.errno != errno.ENOENT:
                raise Exception(ex)
        try:
            os.symlink(self.compose_dir, symlink)
        except Exception as ex:
            self.compose.log_error("Couldn't create latest symlink: %s" % ex)
            raise


class VariantsConfig(object):

    """
    This class generates a variants config which can be used with the compose
    object to generate a dnf repo. Right now it only works with modules.
    """

    def __init__(self, updates, builds, variant_id="Server",
                 arches=['x86_64', 'armhfp', 'aarch64', 'i386', 'ppc64', 'ppc64le', 's390x']):
        """
        Args:
              updates (list) - list of Update objects
              builds (list) - list of ModularBuild objects
              variant_id (str) - the type of variant which will be composed
              arches (list) - architectures which should be included in compose
        """
        self.updates = updates
        self.builds = builds
        self.modules = self._generate_module_list()
        self.arches = arches
        self.headers = [
            # https://pagure.io/pungi/blob/master/f/share/variants.dtd
            '<?xml version="1.0" encoding="UTF-8"?>',
            ('<!DOCTYPE variants PUBLIC "-//Red Hat, Inc.//DTD '
             'Variants info//EN" "variants2012.dtd">'),
        ]
        self.body = [
            '<variants>',
            '<variant id="%s" name="%s" type="variant">' % (variant_id, variant_id),
            '<arches>',
            ''.join(['<arch>%s</arch>' % arch for arch in self.arches]),
            '</arches>',
            '<modules>',
            ''.join(['<module>%s</module>' % module for module in self.modules]),
            '</modules>',
            '</variant>',
            '</variants>'
        ]

    def _generate_module_list(self):
        """
        Generates a list of NSV which should be used for pungi modular compose

        Returns:
          list: list of NSV string which should be composed
        """
        newest_builds = {}
        # we loop through builds so we get rid of older builds and get only
        # a dict with the newest builds
        for build in self.builds:
            nsv = build.nvr.rsplit('-', 1)
            ns = nsv[0]
            version = nsv[1]

            if ns in newest_builds:
                curr_version = newest_builds[ns]
                if int(curr_version) < int(version):
                    newest_builds[ns] = version
            else:
                newest_builds[ns] = version

        # make sure that the modules we want to update get their correct versions
        for update in self.updates:
            for build in update.builds:
                nsv = build.nvr.rsplit('-', 1)
                ns = nsv[0]
                version = nsv[1]
                newest_builds[ns] = version

        module_list = ["%s-%s" % (nstream, v) for nstream, v in newest_builds.iteritems()]
        return module_list

    @property
    def xml(self):
        """
        Returns string xml representation of the object.

        Returns:
            str: xml string
        """
        headers_str = "".join(self.headers)
        body_str = "".join(self.body)
        return str(headers_str + body_str)


def get_pungi_conf(path):
        """
        Reads the config from the provided path

        Args:
            path (string) - this holds the path to the config file.
        """
        config = kobo.conf.PyConfigParser()
        config.load_from_file(path)
        errors, warnings = pungi.checks.validate(config)
        if warnings:
            for warning in warnings:
                log.warning(warning)

        if errors:
            for error in errors:
                log.error(error)
            raise Exception(str(errors))
        return config
