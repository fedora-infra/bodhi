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
import logging
import os
import shutil
import tempfile

from kitchen.text.converters import to_bytes
from urlgrabber.grabber import urlgrab
import createrepo_c as cr

from bodhi.server.buildsys import get_session
from bodhi.server.config import config
from bodhi.server.models import RpmBuild, UpdateStatus, UpdateRequest, UpdateSuggestion


__version__ = '2.0'
log = logging.getLogger(__name__)


class ExtendedMetadata(object):
    """This class represents the updateinfo.xml yum metadata.

    It is generated during push time by the bodhi masher based on koji tags
    and is injected into the yum repodata using the `modifyrepo_c` tool,
    which is included in the `createrepo_c` package.

    """
    def __init__(self, release, request, db, path):
        self.repo = path
        log.debug('repo = %r' % self.repo)
        self.request = request
        if request is UpdateRequest.stable:
            self.tag = release.stable_tag
        else:
            self.tag = release.testing_tag
        self.repo_path = os.path.join(self.repo, self.tag)

        self.db = db
        self.updates = set()
        self.builds = {}
        self.missing_ids = []
        self._from = config.get('bodhi_email')
        self._fetch_updates()

        self.uinfo = cr.UpdateInfo()

        self.hash_type = cr.SHA256
        self.comp_type = cr.XZ

        if release.id_prefix == u'FEDORA-EPEL':
            # yum on py2.4 doesn't support sha256 (#1080373)
            if 'el5' in self.repo or '5E' in self.repo:
                self.hash_type = cr.SHA1
                self.comp_type = cr.GZ
            else:
                # FIXME: I'm not sure which versions of RHEL support xz metadata
                # compression, so use the lowest common denominator for now.
                self.comp_type = cr.BZ2

        # Load from the cache if it exists
        self.cached_repodata = os.path.join(self.repo, '..', self.tag +
                                            '.repocache', 'repodata/')
        if os.path.isfile(os.path.join(self.cached_repodata, 'repomd.xml')):
            log.info('Loading cached updateinfo.xml')
            self._load_cached_updateinfo()
        else:
            log.info("Generating new updateinfo.xml")
            self.uinfo = cr.UpdateInfo()
            for update in self.updates:
                if update.alias:
                    self.add_update(update)
                else:
                    self.missing_ids.append(update.title)

        if self.missing_ids:
            log.error("%d updates with missing ID: %r" % (
                len(self.missing_ids), self.missing_ids))

    def _load_cached_updateinfo(self):
        """
        Load the cached updateinfo.xml from '../{tag}.repocache/repodata'
        """
        seen_ids = set()
        from_cache = set()
        existing_ids = set()

        # Parse the updateinfo out of the repomd
        updateinfo = None
        repomd_xml = os.path.join(self.cached_repodata, 'repomd.xml')
        repomd = cr.Repomd()
        cr.xml_parse_repomd(repomd_xml, repomd)
        for record in repomd.records:
            if record.type == 'updateinfo':
                updateinfo = os.path.join(os.path.dirname(
                    os.path.dirname(self.cached_repodata)),
                    record.location_href)
                break

        assert updateinfo, 'Unable to find updateinfo'

        # Load the metadata with createrepo_c
        log.info('Loading cached updateinfo: %s', updateinfo)
        uinfo = cr.UpdateInfo(updateinfo)

        # Determine which updates are present in the cache
        for update in uinfo.updates:
            existing_ids.add(update.id)

        # Generate metadata for any new builds
        for update in self.updates:
            seen_ids.add(update.alias)
            if not update.alias:
                self.missing_ids.append(update.title)
                continue
            if update.alias in existing_ids:
                notice = None
                for value in uinfo.updates:
                    if value.title == update.title:
                        notice = value
                        break
                if not notice:
                    log.warn('%s ID in cache but notice cannot be found', update.title)
                    self.add_update(update)
                    continue
                if notice.updated_date:
                    if notice.updated_date < update.date_modified:
                        log.debug('Update modified, generating new notice: %s' % update.title)
                        self.add_update(update)
                    else:
                        log.debug('Loading updated %s from cache' % update.title)
                        from_cache.add(update.alias)
                elif update.date_modified:
                    log.debug('Update modified, generating new notice: %s' % update.title)
                    self.add_update(update)
                else:
                    log.debug('Loading %s from cache' % update.title)
                    from_cache.add(update.alias)
            else:
                log.debug('Adding new update notice: %s' % update.title)
                self.add_update(update)

        # Add all relevant notices from the cache to this document
        for notice in uinfo.updates:
            if notice.id in from_cache:
                log.debug('Keeping existing notice: %s', notice.title)
                self.uinfo.append(notice)
            else:
                # Keep all security notices in the stable repo
                if self.request is not UpdateRequest.testing:
                    if notice.type == 'security':
                        if notice.id not in seen_ids:
                            log.debug('Keeping existing security notice: %s',
                                      notice.title)
                            self.uinfo.append(notice)
                        else:
                            log.debug('%s already added?', notice.title)
                    else:
                        log.debug('Purging cached stable notice %s', notice.title)
                else:
                    log.debug('Purging cached testing update %s', notice.title)

    def _fetch_updates(self):
        """Based on our given koji tag, populate a list of Update objects"""
        log.debug("Fetching builds tagged with '%s'" % self.tag)
        kojiBuilds = get_session().listTagged(self.tag, latest=True)
        nonexistent = []
        log.debug("%d builds found" % len(kojiBuilds))
        for build in kojiBuilds:
            self.builds[build['nvr']] = build
            build_obj = self.db.query(RpmBuild).filter_by(nvr=unicode(build['nvr'])).first()
            if build_obj:
                if build_obj.update:
                    self.updates.add(build_obj.update)
                else:
                    log.warn('%s does not have a corresponding update' % build['nvr'])
            else:
                nonexistent.append(build['nvr'])
        if nonexistent:
            log.warning("Couldn't find the following koji builds tagged as "
                        "%s in bodhi: %s" % (self.tag, nonexistent))

    def add_update(self, update):
        """Generate the extended metadata for a given update"""
        rec = cr.UpdateRecord()
        rec.version = __version__
        rec.fromstr = config.get('bodhi_email')
        rec.status = update.status.value
        rec.type = update.type.value
        rec.id = to_bytes(update.alias)
        rec.title = to_bytes(update.title)
        rec.summary = to_bytes('%s %s update' % (update.get_title(),
                                                 update.type.value))
        rec.description = to_bytes(update.notes)
        rec.release = to_bytes(update.release.long_name)
        rec.rights = config.get('updateinfo_rights')

        if update.date_pushed:
            rec.issued_date = update.date_pushed
        if update.date_modified:
            rec.updated_date = update.date_modified

        col = cr.UpdateCollection()
        col.name = to_bytes(update.release.long_name)
        col.shortname = to_bytes(update.release.name)

        koji = get_session()
        for build in update.builds:
            try:
                kojiBuild = self.builds[build.nvr]
            except:
                kojiBuild = koji.getBuild(build.nvr)

            rpms = koji.listBuildRPMs(kojiBuild['id'])
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

                # TODO: how do we handle UpdateSuggestion.logout, etc?
                pkg.reboot_suggested = update.suggest is UpdateSuggestion.reboot

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
            ref.id = to_bytes(bug.bug_id)
            ref.href = to_bytes(bug.url)
            ref.title = to_bytes(bug.title)
            rec.append_reference(ref)

        # Create references for each CVE
        for cve in update.cves:
            ref = cr.UpdateReference()
            ref.type = 'cve'
            ref.id = to_bytes(cve.cve_id)
            ref.href = to_bytes(cve.url)
            rec.append_reference(ref)

        self.uinfo.append(rec)

    def insert_updateinfo(self):
        fd, name = tempfile.mkstemp()
        os.write(fd, self.uinfo.xml_dump().encode('utf-8'))
        os.close(fd)
        self.modifyrepo(name)
        os.unlink(name)

    def modifyrepo(self, filename):
        """Inject a file into the repodata for each architecture"""
        for arch in os.listdir(self.repo_path):
            repodata = os.path.join(self.repo_path, arch, 'repodata')
            log.info('Inserting %s into %s', filename, repodata)
            uinfo_xml = os.path.join(repodata, 'updateinfo.xml')
            shutil.copyfile(filename, uinfo_xml)
            repomd_xml = os.path.join(repodata, 'repomd.xml')
            repomd = cr.Repomd(repomd_xml)
            uinfo_rec = cr.RepomdRecord('updateinfo', uinfo_xml)
            uinfo_rec_comp = uinfo_rec.compress_and_fill(self.hash_type, self.comp_type)
            uinfo_rec_comp.rename_file()
            uinfo_rec_comp.type = 'updateinfo'
            repomd.set_record(uinfo_rec_comp)
            with file(repomd_xml, 'w') as repomd_file:
                repomd_file.write(repomd.xml_dump())
            os.unlink(uinfo_xml)

    def insert_pkgtags(self):
        """Download and inject the pkgtags sqlite from fedora-tagger"""
        if config.get('pkgtags_url'):
            try:
                tags_url = config.get('pkgtags_url')
                tempdir = tempfile.mkdtemp('bodhi')
                local_tags = os.path.join(tempdir, 'pkgtags.sqlite')
                log.info('Downloading %s' % tags_url)
                urlgrab(tags_url, filename=local_tags)
                self.modifyrepo(local_tags)
            except:
                log.exception("There was a problem injecting pkgtags")
            finally:
                shutil.rmtree(tempdir)

    def cache_repodata(self):
        arch = os.listdir(self.repo_path)[0]  # Take the first arch
        repodata = os.path.join(self.repo_path, arch, 'repodata')
        if not os.path.isdir(repodata):
            log.warning('Cannot find repodata to cache: %s' % repodata)
            return
        cache = self.cached_repodata
        if os.path.isdir(cache):
            shutil.rmtree(cache)
        shutil.copytree(repodata, cache)
        log.info('%s cached to %s' % (repodata, cache))
