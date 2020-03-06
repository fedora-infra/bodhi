# Copyright 2007-2019 Red Hat, Inc. and others.
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
"""Define tools for interacting with the build system and a fake build system for development."""

import logging
import time
import typing
import os
from functools import wraps
from threading import Lock

import backoff
import koji

if typing.TYPE_CHECKING:  # pragma: no cover
    from bodhi.server.config import BodhiConfig  # noqa: 401


log = logging.getLogger('bodhi')
_buildsystem = None
_buildsystem_login_lock = Lock()
# URL of the koji hub
_koji_hub = None


def multicall_enabled(func: typing.Callable[..., typing.Any]) -> typing.Callable[..., typing.Any]:
    """
    Decorate the given callable to enable multicall handling.

    This is used by DevBuildsys methods.

    Args:
        func: The function to wrap.
    Returns:
        A wrapped version of func.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs) -> typing.Any:
        """
        If multicall is enabled, store the results from func on self.

        If multicall is not enabled, just call func and return its results as per usual.
        """
        if not self.multicall:
            return func(self, *args, **kwargs)

        # disable multicall during execution, so that inner func calls to other
        # methods don't append their results as well
        self._multicall = False
        result = func(self, *args, **kwargs)
        self.multicall_result.append([result])
        self._multicall = True
    return wrapper


class DevBuildsys:
    """A dummy buildsystem instance used during development and testing."""

    _side_tag_data = [{'id': 1234, 'name': 'f17-build-side-1234'},
                      {'id': 7777, 'name': 'f17-build-side-7777'}]

    __untag__ = []  # type: typing.List[typing.Tuple[str, str]]
    __moved__ = []  # type: typing.List[typing.Tuple[str, str, str]]
    __added__ = []  # type: typing.List[typing.Tuple[str, str]]
    __tagged__ = {}  # type: typing.Mapping[str, typing.List[str]]
    __rpms__ = []  # type: typing.List[typing.Dict[str, object]]
    __tags__ = []  # type: typing.List[typing.Tuple[str, typing.Mapping[str, typing.Any]]]
    __side_tags__ = _side_tag_data  # type: typing.List[typing.Dict[str, object]]
    __removed_side_tags__ = []  # type: typing.List[typing.Dict[str, object]]

    _build_data = {'build_id': 16058,
                   'completion_time': '2007-08-24 23:26:10.890319',
                   'completion_ts': 1187997970,
                   'creation_event_id': 151517,
                   'creation_time': '2007-08-24 19:38:29.422344',
                   'extra': None,
                   'epoch': None,
                   'owner_id': 388,
                   'owner_name': 'lmacken',
                   'package_id': 8,
                   'state': 1,
                   'tag_id': 19,
                   'task_id': 127621}

    def __init__(self):
        """Initialize the DevBuildsys."""
        self._multicall = False
        self.multicall_result = []

    @property
    def _side_tag_ids_names(self):
        return {id_or_name
                for taginfo in self._side_tag_data
                for id_or_name in (taginfo['id'], taginfo['name'])}

    @property
    def multicall(self) -> bool:
        """
        Return the value of self._multicall.

        Returns:
            object: The value of self._multicall.
        """
        return self._multicall

    @multicall.setter
    def multicall(self, value: bool):
        """
        Set the _multicall attribute to the given value.

        Args:
            value: The value to set the _multicall attribute to.
        """
        self._multicall = value
        self.multicall_result = []

    @classmethod
    def clear(cls):
        """Clear the state of the class variables."""
        cls.__untag__ = []
        cls.__moved__ = []
        cls.__added__ = []
        cls.__tagged__ = {}
        cls.__rpms__ = []
        cls.__tags__ = []
        cls.__side_tags__ = list(cls._side_tag_data)
        cls.__removed_side_tags__ = []

    def multiCall(self):
        """Emulate Koji's multiCall."""
        result = self.multicall_result
        self.multicall = False
        return result

    def moveBuild(self, from_tag: str, to_tag: str, build: str, *args, **kw):
        """Emulate Koji's moveBuild."""
        if to_tag is None:
            raise RuntimeError('Attempt to tag {} with None.'.format(build))
        log.debug("moveBuild(%s, %s, %s)" % (from_tag, to_tag, build))
        DevBuildsys.__moved__.append((from_tag, to_tag, build))

    def tagBuild(self, tag: str, build: str, *args, **kw):
        """Emulate Koji's tagBuild."""
        if tag is None:
            raise RuntimeError('Attempt to tag {} with None.'.format(build))
        log.debug("tagBuild(%s, %s)" % (tag, build))
        DevBuildsys.__added__.append((tag, build))

    def untagBuild(self, tag: str, build: str, *args, **kw):
        """Emulate Koji's untagBuild."""
        if tag is None:
            raise RuntimeError('Attempt to untag {} with None.'.format(build))
        log.debug("untagBuild(%s, %s)" % (tag, build))
        DevBuildsys.__untag__.append((tag, build))

    def ssl_login(self, *args, **kw):
        """Emulate Koji's ssl_login."""
        log.debug("ssl_login(%s, %s)" % (args, kw))

    def taskFinished(self, task: int) -> bool:
        """Emulate Koji's taskFinished."""
        return True

    def getTaskInfo(self, task: int) -> typing.Mapping[str, int]:
        """Emulate Koji's getTaskInfo."""
        return {'state': koji.TASK_STATES['CLOSED']}

    def getTaskRequest(self, task_id: int) -> typing.List[typing.Union[str, typing.Mapping]]:
        """Emulate Koji's getTaskRequest."""
        return [
            'git://pkgs.fedoraproject.org/rpms/bodhi?#2e994ca8b3296e62e8b0aadee1c5c0649559625a',
            'f17-candidate', {}]

    def listPackages(self) -> typing.List[typing.Mapping[str, typing.Union[int, str]]]:
        """Emulate Koji's listPackages."""
        return [
            {'package_id': 2625, 'package_name': 'nethack'},
        ]

    @multicall_enabled
    def getBuild(self, build='TurboGears-1.0.2.2-2.fc17', other=False, testing=False):
        """Emulate Koji's getBuild."""
        # needed to test against non-existent builds
        if 'youdontknowme' in build:
            return None

        if 'gnome-backgrounds-3.0-1.fc17' in build:
            return {'name': 'gnome-backgrounds',
                    'nvr': 'gnome-backgrounds-3.0-1.fc17',
                    'package_name': 'gnome-backgrounds',
                    'release': '1.fc17',
                    'tag_name': 'f17-build-side-7777',
                    'version': '3.0'}

        theid = 16058
        if other and not testing:
            theid = 16059
        elif other and testing:
            theid = 16060

        data = self._build_data.copy()
        data['id'] = theid
        if 'noowner' in build:
            del data['owner_name']

        name, version, release = build.rsplit("-", 2)
        release_tokens = release.split(".")

        for token in release_tokens:
            # Starting to hardcode some dev buildsys bits for docker.
            # See https://github.com/fedora-infra/bodhi/pull/1543
            if token.endswith("container") or token.endswith("flatpak"):
                fedora_release = "f" + (token
                                        .replace("fc", "")
                                        .replace("flatpak", "")
                                        .replace("container", ""))
                tag = "%s-updates-testing" % fedora_release

                format_data = {
                    'registry': 'candidate-registry.fedoraproject.org',
                    'hash': 'sha256:2bd64a888...',
                    'version': version,
                    'release': release
                }

                if token.endswith("flatpak"):
                    format_data['repository'] = name
                else:
                    tag = "f%s-updates-testing" % token.replace("fc", "").replace("container", "")
                    format_data['repository'] = "{}/{}".format(fedora_release, name)

                data['extra'] = {
                    'container_koji_task_id': 19708268,
                    'image': {
                        'index': {
                            'pull': ['{registry}/{repository}@sha256:{hash}'
                                     .format(**format_data),
                                     '{registry}/{repository}:{version}-{release}'
                                     .format(**format_data)],
                        }
                    },
                }

                if token.endswith("flatpak"):
                    data['extra']['image']['flatpak'] = True

                break

            # Hardcoding for modules in the dev buildsys
            if token.startswith("2017"):
                tag = "f27M-updates-testing"
                data['extra'] = {
                    'typeinfo': {'module': {'more': 'mbs stuff goes here'}}
                }
                break

            if token.startswith("fc"):
                if testing:
                    tag = "f%s-updates-testing" % token.replace("fc", "")
                    break
                else:
                    tag = "f%s-updates-candidate" % token.replace("fc", "")
                    break

            if token.startswith("el"):
                tag = "dist-%sE-epel-testing-candidate" % token.replace("el", "")
                break
        else:
            raise ValueError("Couldn't determine dist for build '%s'" % build)

        if other:
            if testing:
                release_tokens[0] = str(int(release_tokens[0]) + 2)
            else:
                release_tokens[0] = str(int(release_tokens[0]) + 1)
            release = ".".join(release_tokens)
            build = "%s-%s-%s" % (name, version, release)

        data.update({'name': name,
                     'nvr': build,
                     'package_name': name,
                     'release': release,
                     'tag_name': tag,
                     'version': version})

        if 'testmissingnvr' in build:
            del data['nvr']

        return data

    def listBuildRPMs(self, id: int, *args, **kw) -> typing.List[typing.Dict[str, object]]:
        """Emulate Koji's listBuildRPMs."""
        rpms = [{'arch': 'src',
                 'build_id': 6475,
                 'buildroot_id': 1883,
                 'buildtime': 1178868422,
                 'epoch': None,
                 'id': 62330,
                 'name': 'TurboGears',
                 'nvr': 'TurboGears-1.0.2.2-2.fc17',
                 'payloadhash': '6787febe92434a9be2a8f309d0e2014e',
                 'release': '2.fc17',
                 'size': 761742,
                 'version': '1.0.2.2'},
                {'arch': 'noarch',
                 'build_id': 6475,
                 'buildroot_id': 1883,
                 'buildtime': 1178868537,
                 'epoch': None,
                 'id': 62331,
                 'name': 'TurboGears',
                 'nvr': 'TurboGears-1.0.2.2-2.fc17',
                 'payloadhash': 'f3ec9bdce453816f94283a15a47cb952',
                 'release': '2.fc17',
                 'size': 1993385,
                 'version': '1.0.2.2'},
                ]
        if id == 16059:  # for updateinfo.xml tests
            rpms[0]['nvr'] = rpms[1]['nvr'] = 'TurboGears-1.0.2.2-3.fc17'
            rpms[0]['release'] = rpms[1]['release'] = '3.fc17'
        rpms += DevBuildsys.__rpms__
        return rpms

    def listTags(self, build: str, *args, **kw) -> typing.List[typing.Dict[str, object]]:
        """Emulate Koji's listTags."""
        if 'el5' in build or 'el6' in build:
            release = build.split('.')[-1].replace('el', '')
            result = [
                {'arches': 'i386 x86_64 ppc ppc64', 'id': 10, 'locked': True,
                 'name': 'dist-%sE-epel-testing-candidate' % release, 'perm': None,
                 'perm_id': None},
                {'arches': 'i386 x86_64 ppc ppc64', 'id': 10, 'locked': True,
                 'name': 'dist-%sE-epel-testing-candidate' % release, 'perm': None,
                 'perm_id': None},
                {'arches': 'i386 x86_64 ppc ppc64', 'id': 5, 'locked': True,
                 'name': 'dist-%sE-epel' % release, 'perm': None, 'perm_id': None}]
        elif 'el7' in build:
            release = build.split('.')[-1].replace('el', 'epel')
            result = [
                {'arches': 'i386 x86_64 ppc ppc64', 'id': 10, 'locked': True,
                 'name': '%s-testing-candidate' % release, 'perm': None, 'perm_id': None},
                {'arches': 'i386 x86_64 ppc ppc64', 'id': 5, 'locked': True, 'name': '%s' % release,
                 'perm': None, 'perm_id': None},
                {'arches': 'i386 x86_64 ppc ppc64', 'id': 5, 'locked': True,
                 'name': '%s-testing' % release, 'perm': None, 'perm_id': None}]
        elif '-master-' in build or build.startswith(('nodejs-6-', 'nodejs-8-', 'nodejs-9-')):
            # Hardcoding for modules in the dev buildsys
            result = [
                {'arches': 'x86_64', 'id': 15, 'locked': True,
                 'name': 'f27M-updates-candidate'},
                {'arches': 'x86_64', 'id': 16, 'locked': True,
                 'name': 'f27M-updates-testing'},
                {'arches': 'x86_64', 'id': 17, 'locked': True,
                 'name': 'f27M'},
            ]
        elif 'container' in build:
            result = [
                {'arches': 'x86_64', 'id': 15, 'locked': True,
                 'name': 'f28C-updates-candidate'},
                {'arches': 'x86_64', 'id': 16, 'locked': True,
                 'name': 'f28C-updates-testing'},
                {'arches': 'x86_64', 'id': 17, 'locked': True,
                 'name': 'f28C'},
            ]
        elif 'flatpak' in build:
            result = [
                {'arches': 'x86_64', 'id': 15, 'locked': True,
                 'name': 'f28F-updates-candidate'},
                {'arches': 'x86_64', 'id': 16, 'locked': True,
                 'name': 'f28F-updates-testing'},
                {'arches': 'x86_64', 'id': 17, 'locked': True,
                 'name': 'f28F'},
            ]
        else:
            release = build.split('.')[-1].replace('fc', 'f')
            result = [
                {'arches': 'i386 x86_64 ppc ppc64', 'id': 10, 'locked': True,
                 'name': '%s-updates-candidate' % release, 'perm': None, 'perm_id': None},
                {'arches': 'i386 x86_64 ppc ppc64', 'id': 5, 'locked': True, 'name': '%s' % release,
                 'perm': None, 'perm_id': None},
                {'arches': 'i386 x86_64 ppc ppc64', 'id': 5, 'locked': True,
                 'name': '%s-updates-testing' % release, 'perm': None, 'perm_id': None}]
        if build in DevBuildsys.__tagged__:
            for tag in DevBuildsys.__tagged__[build]:
                result += [{'name': tag}]
        return result

    @multicall_enabled
    def listTagged(self, tag: str, *args, **kw) -> typing.List[typing.Any]:
        """List updates tagged with teh given tag."""
        latest = kw.get('latest', False)
        if tag in self._side_tag_ids_names:
            return [self.getBuild(build="gnome-backgrounds-3.0-1.fc17")]
        builds = []

        all_builds = [self.getBuild(),
                      self.getBuild(other=True),
                      self.getBuild(other=True, testing=True)]

        if latest:
            # Delete all older builds which aren't the latest for their tag.
            # Knowing which these are is simpler than trying to rpmvercmp.
            del all_builds[0]

        for build in all_builds:
            if build['nvr'] in self.__untag__:
                log.debug('Pruning koji build %s' % build['nvr'])
                continue
            elif build['tag_name'] == tag:
                builds.append(build)
        for build in DevBuildsys.__tagged__:
            for tag_ in DevBuildsys.__tagged__[build]:
                if tag_ == tag:
                    builds.append(self.getBuild(build))
        log.debug(builds)
        return builds

    def getLatestBuilds(self, *args, **kw) -> typing.List[typing.Any]:
        """
        Return a list of the output from self.getBuild().

        Returns:
            list: A list of the latest builds from getBuild().
        """
        return [self.getBuild()]

    @multicall_enabled
    def getTag(self, taginfo, **kw):
        """
        Retrieve the given tag from koji.

        Args:
            taginfo (int or str): The tag you want info about.
            strict (bool): If True, raise an Exception if epel tags are queried. Defaults to False.
        Returns:
            dict or None: A dictionary of tag information, or None if epel is requested and strict
                is False.
        Raises:
            koji.GenericError: If strict is True and epel is requested.
        """
        if isinstance(taginfo, int):
            taginfo = "f%d" % taginfo

        if taginfo.startswith("epel"):
            if kw.get("strict", False):
                raise koji.GenericError("Invalid tagInfo: '%s'" % taginfo)

            else:
                return None

        # These tags needs to be created
        if taginfo in ["f32-build-side-1234-signing-pending",
                       "f32-build-side-1234-testing-pending"]:
            return None

        # emulate a side-tag response
        if taginfo in self._side_tag_ids_names:
            for sidetag in self.__side_tags__:
                if taginfo in (sidetag['id'], sidetag['name']):
                    return {'maven_support': False, 'locked': False, 'name': sidetag['name'],
                            'extra': {'sidetag_user': 'dudemcpants', 'sidetag': True},
                            'perm': None, 'perm_id': None, 'arches': None,
                            'maven_include_all': False, 'id': sidetag['id']}

            if kw.get('strict'):
                raise koji.GenericError("Invalid tagInfo: '%s'" % taginfo)
            else:
                return None

        return {'maven_support': False, 'locked': False, 'name': taginfo,
                'extra': {}, 'perm': None, 'id': 246, 'arches': None,
                'maven_include_all': False, 'perm_id': None}

    def getFullInheritance(self, taginfo, **kw):
        """
        Return a tag inheritance.

        Args:
            taginfo (int or str): The tag. does not impact the output
        Returns:
            list: A list of dicts of tag information
        """
        return [{'intransitive': False, 'name': 'f17-build', 'pkg_filter': '', 'priority': 0,
                 'parent_id': 6448, 'maxdepth': None, 'noconfig': False, 'child_id': 7715,
                 'nextdepth': None, 'filter': [], 'currdepth': 1},
                {'intransitive': False, 'name': 'f17-override', 'pkg_filter': '', 'priority': 0,
                 'parent_id': 6447, 'maxdepth': None, 'noconfig': False, 'child_id': 6448,
                 'nextdepth': None, 'filter': [], 'currdepth': 2},
                {'intransitive': False, 'name': 'f17-updates', 'pkg_filter': '', 'priority': 0,
                 'parent_id': 6441, 'maxdepth': None, 'noconfig': False, 'child_id': 6447,
                 'nextdepth': None, 'filter': [], 'currdepth': 3},
                {'intransitive': False, 'name': 'f17', 'pkg_filter': '', 'priority': 0,
                 'parent_id': 6438, 'maxdepth': None, 'noconfig': False, 'child_id': 6441,
                 'nextdepth': None, 'filter': [], 'currdepth': 4}]

    def listSideTags(self, **kw):
        """Return a list of side-tags."""
        return self.__side_tags__

    def createTag(self, tag: str, **opts):
        """Emulate tag adding."""
        if 'parent' not in opts:
            raise ValueError('No parent in tag options')
        for nr in self.__tags__:
            if self.__tags__[0] == tag:
                raise ValueError('Tag %s already exists' % tag)
        opts['locked'] = False
        opts['maven_support'] = False
        opts['name'] = tag
        opts['perm'] = 'admin'
        opts['arches'] = None
        opts['maven_include_all'] = False
        opts['perm_id'] = 1
        self.__tags__.append((tag, opts))

    def editTag2(self, *args, **kw):
        """Edit a tag."""
        pass

    def deleteTag(self, tagid: typing.Union[str, int]):
        """Emulate tag deletion."""
        if isinstance(tagid, str):
            for tid, tinfo in self.__tags__:
                if tagid == tid:
                    self.__tags__.remove((tid, tinfo))
                    return
        else:
            del self.__tags__[tagid]

    def removeSideTag(self, side_tag):
        """Emulate side-tag and build target deletion."""
        if isinstance(side_tag, int):
            what = 'id'
        elif isinstance(side_tag, str):
            what = 'name'
        else:
            raise TypeError(f'sidetag: {side_tag!r}')

        matching_tags = [t for t in self.__side_tags__ if t[what] == side_tag]

        if not matching_tags:
            raise koji.GenericError(f"Not a sidetag: {side_tag}")

        self.__side_tags__.remove(matching_tags[0])
        self.__removed_side_tags__.append(matching_tags[0])

    def getRPMHeaders(self, rpmID: str,
                      headers: typing.Any) -> typing.Union[typing.Mapping[str, str], None]:
        """
        Return headers for the given RPM.

        Args:
            rpmID: The RPM you want headers for.
            headers: Unused.
        Returns:
            A dictionary of RPM headers, or None if the rpmID is not found.
        """
        if rpmID == 'raise-exception.src':
            raise Exception
        elif rpmID == 'do-not-find-anything.src':
            return None
        else:
            headers = {
                'description': (
                    "The libseccomp library provides an easy to use interface to the "
                    "Linux Kernel's\nsyscall filtering mechanism, seccomp. The "
                    "libseccomp API allows an application\nto specify which "
                    "syscalls, and optionally which syscall arguments, the\n"
                    "application is allowed to execute, all of which are "
                    "enforced by the Linux\nKernel."),
                'url': 'http://libseccomp.sourceforge.net',
                'changelogname': [
                    'Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.1.0-1',
                    'Paul Moore <pmoore@redhat.com> - 2.1.0-0',
                    'Paul Moore <pmoore@redhat.com> - 2.0.0-0',
                    'Paul Moore <pmoore@redhat.com> - 1.0.1-0',
                    'Paul Moore <pmoore@redhat.com> - 1.0.0-0',
                    'Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 0.1.0-2',
                    'Paul Moore <pmoore@redhat.com> - 0.1.0-1',
                    'Paul Moore <pmoore@redhat.com> - 0.1.0-0'],
                'summary': 'Enhanced seccomp library',
                'version': '2.1.0',
                'changelogtime': [
                    1375531200, 1370952000, 1359374400, 1352808000, 1343736000,
                    1342699200, 1341921600, 1339502400],
                'changelogtext': [
                    '- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild',
                    '- New upstream version\n- Added support for the ARM architecture\n'
                    '- Added the scmp_sys_resolver tool',
                    '- New upstream version',
                    '- New upstream version with several important fixes',
                    '- New upstream version\n- Remove verbose build patch as it is no '
                    'longer needed\n- Enable _smp_mflags during build stage',
                    '- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild',
                    '- Limit package to x86/x86_64 platforms (RHBZ #837888)',
                    '- Initial version'],
                'release': '1.fc20',
                'name': 'libseccomp'
            }
            if rpmID == "TurboGears-2.0.0.0-1.fc17.src":
                headers['changelogname'].insert(0, 'Randy Barlow <bowlofeggs@fp.o> - 2.2.0-1')
                headers['changelogtext'].insert(0, '- Added some bowlofeggs charm.')
                headers['changelogtime'].insert(0, 1375531201)
            elif rpmID == 'TurboGears-1.9.1-1.fc17.src':
                headers['changelogtext'] = []
            elif rpmID == 'TurboGears-1.9.1-42.fc17.src':
                # Make sure only a single changelog entry is present
                headers['changelogname'] = ['Randy Barlow <bowlofeggs@fp.o> - 1.9.1-42']
                headers['changelogtext'] = ["- Hope I didn't break anything!"]
                headers['changelogtime'] = [1375531200]
            return headers


@backoff.on_exception(backoff.expo, koji.AuthError, max_time=600)
def koji_login(config: 'BodhiConfig', authenticate: bool) -> koji.ClientSession:
    """
    Login to Koji and return the session.

    Args:
        config: Bodhi's configuration dictionary.
        authenticate: If True, establish an authenticated client session.
    Returns:
        An authenticated Koji ClientSession that is ready to use.
    """
    koji_options = {
        'krb_rdns': False,
        'max_retries': 30,
        'retry_interval': 10,
        'offline_retry': True,
        'offline_retry_interval': 10,
        'anon_retry': True,
    }

    koji_client = koji.ClientSession(_koji_hub, koji_options)
    if authenticate and not koji_client.krb_login(**get_krb_conf(config)):
        log.error('Koji krb_login failed')
    return koji_client


def get_krb_conf(config: 'BodhiConfig') -> typing.Mapping[str, str]:
    """
    Return arguments for krb_login.

    Args:
        config: Bodhi's configuration dictionary.
    Returns:
        A dictionary containing three keys:
            principal: The kerberos principal to use.
            keytab: The kerberos keytab to use.
            ccache: The kerberos ccache to use.
    """
    principal = config.get('krb_principal')
    keytab = config.get('krb_keytab')
    ccache = config.get('krb_ccache')
    args = {}
    if principal:
        args['principal'] = principal
    if keytab:
        args['keytab'] = keytab
    if ccache:
        ccache = ccache.replace('%{uid}', str(os.geteuid()))
        args['ccache'] = ccache
    return args


def get_session() -> typing.Union[koji.ClientSession, DevBuildsys]:
    """
    Get a new buildsystem instance.

    Returns:
        A buildsystem client instance.
    Raises:
        RuntimeError: If the build system has not been initialized. See setup_buildsystem().
    """
    global _buildsystem
    if _buildsystem is None:
        raise RuntimeError('Buildsys needs to be setup')
    with _buildsystem_login_lock:
        return _buildsystem()


def teardown_buildsystem():
    """Tear down the build system."""
    global _buildsystem
    _buildsystem = None
    DevBuildsys.clear()


def setup_buildsystem(settings: 'BodhiConfig', authenticate: bool = True):
    """
    Initialize the buildsystem client.

    Args:
        settings: Bodhi's config.
        authenticate: If True, establish an authenticated Koji session. Defaults to True.
    Raises:
        ValueError: If the buildsystem is configured to an invalid value.
    """
    global _buildsystem, _koji_hub
    if _buildsystem:
        return

    _koji_hub = settings.get('koji_hub')
    buildsys = settings.get('buildsystem')

    if buildsys == 'koji':
        log.debug('Using Koji Buildsystem')

        def get_koji_login():
            """Call koji_login with settings and return the result."""
            return koji_login(config=settings, authenticate=authenticate)

        _buildsystem = get_koji_login
    elif buildsys in ('dev', 'dummy', None):
        log.debug('Using DevBuildsys')
        _buildsystem = DevBuildsys
    else:
        raise ValueError('Buildsys %s not known' % buildsys)


def wait_for_tasks(
        tasks: typing.List[typing.Any],
        session: typing.Union[koji.ClientSession, None] = None,
        sleep: int = 300) -> typing.List[typing.Any]:
    """
    Wait for a list of koji tasks to complete.

    Args:
        tasks: The return value of Koji's multiCall().
        session: A Koji client session to use. If not provided, the
            function will acquire its own session.
        sleep: How long to sleep between polls on Koji when waiting for tasks to complete.
    Returns:
        A list of failed tasks. An empty list indicates that all tasks completed successfully.
    """
    log.debug("Waiting for %d tasks to complete: %s" % (len(tasks), tasks))
    failed_tasks = []
    if not session:
        session = get_session()
    for task in tasks:
        if not task:
            log.debug("Skipping task: %s" % task)
            continue
        while not session.taskFinished(task):
            time.sleep(sleep)
        task_info = session.getTaskInfo(task)
        if task_info['state'] != koji.TASK_STATES['CLOSED']:
            log.error("Koji task %d failed" % task)
            failed_tasks.append(task)
    log.debug("%d tasks completed successfully, %d tasks failed." % (
        len(tasks) - len(failed_tasks), len(failed_tasks)))
    return failed_tasks
