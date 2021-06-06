# Copyright 2007-2019 Red Hat, Inc. and others.
#
# This file is part of Bodhi.
#
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
"""Create metadata files when composing repositories."""
import logging
import os
import shelve
import shutil
import tempfile

import createrepo_c as cr

from bodhi.server import util
from bodhi.server.buildsys import get_session
from bodhi.server.config import config
from bodhi.server.models import Build, UpdateStatus, UpdateRequest, UpdateSuggestion


__version__ = '2.0'
log = logging.getLogger(__name__)


def insert_in_repo(comp_type, repodata, filetype, extension, source, zchunk):
    """
    Inject a file into the repodata with the help of createrepo_c.

    Args:
        comp_type (int): createrepo_c compression type indication.
        repodata (str): The path to the repo where the metadata will be inserted.
        filetype (str): What type of metadata will be inserted by createrepo_c.
            This does allow any string to be inserted (custom types). There are some
            types which are used with dnf repos as primary, updateinfo, comps, filelist etc.
        extension (str): The file extension (xml, sqlite).
        source (str): A file path. File holds the dump of metadata until
            copied to the repodata folder.
        zchunk (bool): Whether zchunk data is supported for clients of this repo.
    """
    log.info('Inserting %s.%s into %s', filetype, extension, repodata)
    target_fname = os.path.join(repodata, '%s.%s' % (filetype, extension))
    shutil.copyfile(source, target_fname)
    repomd_xml = os.path.join(repodata, 'repomd.xml')
    repomd = cr.Repomd(repomd_xml)
    add_list = [(filetype, comp_type)]
    if zchunk and hasattr(cr, 'ZCK_COMPRESSION') and comp_type != cr.ZCK_COMPRESSION:
        add_list.append((filetype + "_zck", cr.ZCK_COMPRESSION))
    for (ft, ct) in add_list:
        # create a new record for our repomd.xml
        rec = cr.RepomdRecord(ft, target_fname)
        # compress our metadata file with the comp_type
        rec_comp = rec.compress_and_fill(cr.SHA256, ct)
        # add hash to the compressed metadata file
        rec_comp.rename_file()
        # set type of metadata
        rec_comp.type = ft
        # insert metadata about our metadata in repomd.xml
        repomd.set_record(rec_comp)
    with open(repomd_xml, 'w') as repomd_file:
        repomd_file.write(repomd.xml_dump())
    os.unlink(target_fname)


def modifyrepo(comp_type, compose_path, filetype, extension, source, zchunk):
    """
    Inject a file into the repodata for each architecture with the help of createrepo_c.

    Args:
        compose_path (str): The path to the compose where the metadata will be inserted.
        filetype (str): What type of metadata will be inserted by createrepo_c.
            This does allow any string to be inserted (custom types). There are some
            types which are used with dnf repos as primary, updateinfo, comps, filelist etc.
        extension (str): The file extension (xml, sqlite).
        source (str): A file path. File holds the dump of metadata until
            copied to the repodata folder.
        zchunk (bool): Whether zchunk data is supported for clients of this repo.
    """
    repo_path = os.path.join(compose_path, 'compose', 'Everything')
    for arch in os.listdir(repo_path):
        if arch == 'source':
            repodata = os.path.join(repo_path, arch, 'tree', 'repodata')
        else:
            repodata = os.path.join(repo_path, arch, 'os', 'repodata')
        insert_in_repo(comp_type, repodata, filetype, extension, source, zchunk)


class UpdateInfoMetadata(object):
    """
    This class represents the updateinfo.xml yum metadata.

    It is generated during push time by the bodhi composer based on koji tags
    and is injected into the yum repodata using the `modifyrepo_c` tool,
    which is included in the `createrepo_c` package.
    """

    def __init__(self, release, request, db, composedir, close_shelf=True):
        """
        Initialize the UpdateInfoMetadata object.

        Args:
            release (bodhi.server.models.Release): The Release that is being composed.
            request (bodhi.server.models.UpdateRequest): The Request that is being composed.
            db (): A database session to be used for queries.
            composedir (str): A path to the composedir.
            close_shelf (bool): Whether to close the shelve, which is used to cache updateinfo
                between composes.
        """
        self.request = request
        if request is UpdateRequest.stable:
            self.tag = release.stable_tag
        else:
            self.tag = release.testing_tag

        self.db = db
        self.updates = set()
        self.builds = {}
        self._from = config.get('bodhi_email')
        if config.get('cache_dir'):
            self.shelf = shelve.open(os.path.join(config.get('cache_dir'), '%s.shelve' % self.tag))
        else:
            # If we have no cache dir, let's at least cache in-memory.
            self.shelf = {}
            close_shelf = False
        self._fetch_updates()

        self.uinfo = cr.UpdateInfo()

        self.comp_type = cr.XZ

        # Some repos such as FEDORA-EPEL, are primarily targeted at
        # distributions that use the yum client, which does not support zchunk metadata
        self.legacy_repos = ['FEDORA-EPEL']
        self.zchunk = True

        if release.id_prefix in self.legacy_repos:
            # FIXME: I'm not sure which versions of RHEL support xz metadata
            # compression, so use the lowest common denominator for now.
            self.comp_type = cr.BZ2

            log.warning(
                'Zchunk data is disabled for repo {release.id_prefix} until it moves to a client'
                ' with Zchunk support'
            )
            self.zchunk = False

        self.uinfo = cr.UpdateInfo()
        for update in self.updates:
            self.add_update(update)

        if close_shelf:
            self.shelf.close()

    def _fetch_updates(self):
        """Based on our given koji tag, populate a list of Update objects."""
        log.debug("Fetching builds tagged with '%s'" % self.tag)
        kojiBuilds = get_session().listTagged(self.tag, latest=True)
        nonexistent = []
        log.debug("%d builds found" % len(kojiBuilds))
        for build in kojiBuilds:
            self.builds[build['nvr']] = build
            build_obj = self.db.query(Build).filter_by(nvr=str(build['nvr'])).first()
            if build_obj:
                if build_obj.update:
                    self.updates.add(build_obj.update)
                else:
                    log.warning('%s does not have a corresponding update' % build['nvr'])
            else:
                nonexistent.append(build['nvr'])
        if nonexistent:
            log.warning("Couldn't find the following koji builds tagged as "
                        "%s in bodhi: %s" % (self.tag, nonexistent))

    def get_rpms(self, koji, nvr):
        """
        Retrieve the given RPM nvr from the cache if available, or from Koji if not available.

        Args:
            koji (koji.ClientSession): An initialized Koji client.
            nvr (str): The nvr for which you wish to retrieve Koji data.
        Returns:
            list: A list of dictionaries describing all the subpackages that are part of the given
                nvr.
        """
        if str(nvr) in self.shelf:
            return self.shelf[str(nvr)]

        if nvr in self.builds:
            buildid = self.builds[nvr]['id']
        else:
            buildid = koji.getBuild(nvr)['id']

        rpms = koji.listBuildRPMs(buildid)
        self.shelf[str(nvr)] = rpms
        return rpms

    def add_update(self, update):
        """
        Generate the extended metadata for a given update, adding it to self.uinfo.

        Args:
            update (bodhi.server.models.Update): The Update to be added to self.uinfo.
        """
        rec = cr.UpdateRecord()
        rec.version = __version__
        rec.fromstr = config.get('bodhi_email')
        rec.status = update.status.value
        rec.type = update.type.value
        rec.id = update.alias.encode('utf-8')
        rec.title = update.title.encode('utf-8')
        rec.severity = util.severity_updateinfo_str(update.severity.value)
        rec.summary = ('%s %s update' % (update.get_title(),
                                         update.type.value)).encode('utf-8')
        rec.description = update.notes.encode('utf-8')
        rec.release = update.release.long_name.encode('utf-8')
        rec.rights = config.get('updateinfo_rights')

        if update.date_pushed:
            rec.issued_date = update.date_pushed
        else:
            # Sometimes we only set the date_pushed after it's pushed out, however,
            # it seems that Satellite does not like update entries without issued_date.
            # Since we know that we are pushing it now, and the next push will get the data
            # correctly, let's just insert "date submitted".
            rec.issued_date = update.date_submitted
        if update.date_modified:
            rec.updated_date = update.date_modified
        else:
            # Likewise, if there is no date_modified, use date_submitted
            rec.updated_date = update.date_submitted

        col = cr.UpdateCollection()
        col.name = update.release.long_name.encode('utf-8')
        col.shortname = update.release.name.encode('utf-8')

        koji = get_session()
        for build in update.builds:
            rpms = self.get_rpms(koji, build.nvr)
            for rpm in rpms:
                pkg = cr.UpdateCollectionPackage()
                pkg.name = rpm['name']
                pkg.version = rpm['version']
                pkg.release = rpm['release']
                if rpm['epoch'] is not None:
                    pkg.epoch = str(rpm['epoch'])
                else:
                    pkg.epoch = '0'
                pkg.arch = rpm['arch']

                pkg.reboot_suggested = update.suggest == UpdateSuggestion.reboot
                pkg.relogin_suggested = update.suggest == UpdateSuggestion.logout

                filename = '%s.%s.rpm' % (rpm['nvr'], rpm['arch'])
                pkg.filename = filename

                # Build the URL
                if rpm['arch'] == 'src':
                    arch = 'SRPMS'
                elif rpm['arch'] in ('noarch', 'i686'):
                    arch = 'i386'
                else:
                    arch = rpm['arch']

                pkg.src = os.path.join(
                    config.get('file_url'),
                    update.status is UpdateStatus.testing and 'testing' or '',
                    str(update.release.version), arch, filename[0], filename)

                col.append(pkg)

        rec.append_collection(col)

        # Create references for each bug
        for bug in update.bugs:
            ref = cr.UpdateReference()
            ref.type = 'bugzilla'
            ref.id = str(bug.bug_id).encode('utf-8')
            ref.href = bug.url.encode('utf-8')
            ref.title = bug.title.encode('utf-8') if bug.title else ''
            rec.append_reference(ref)

        self.uinfo.append(rec)

    def insert_updateinfo(self, compose_path):
        """
        Add the updateinfo.xml file to the repository.

        Args:
            compose_path (str): The path to the compose where the metadata will be inserted.
        """
        fd, tmp_file_path = tempfile.mkstemp()
        os.write(fd, self.uinfo.xml_dump().encode('utf-8'))
        os.close(fd)
        modifyrepo(self.comp_type,
                   compose_path,
                   'updateinfo',
                   'xml',
                   tmp_file_path,
                   self.zchunk)
        os.unlink(tmp_file_path)
