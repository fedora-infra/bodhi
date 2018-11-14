# -*- coding: utf-8 -*-
# Copyright 2007-2018 Red Hat, Inc. and others.
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

from threading import Lock
import logging
import time
from functools import wraps

import koji


log = logging.getLogger('bodhi')
_buildsystem = None
# URL of the koji hub
_koji_hub = None


def multicall_enabled(func):
    """
    Decorate the given callable to enable multicall handling.

    This is used by DevBuildsys methods.

    Args:
        func (callable): The function to wrap.
    Returns:
        callable: A wrapped version of func.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
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


class Buildsystem(object):
    """
    The parent for our buildsystem.

    Not only does this help us keep track of the functionality that we expect from our buildsystem,
    but it also alows us to create a development subclass of this object to use during development
    so we don't alter any production data.
    """

    def getBuild(self, *args, **kw):
        """Raise NotImplementedError."""
        raise NotImplementedError

    def getLatestBuilds(self, *args, **kw):
        """Raise NotImplementedError."""
        raise NotImplementedError

    def moveBuild(self, *args, **kw):
        """Raise NotImplementedError."""
        raise NotImplementedError

    def ssl_login(self, *args, **kw):
        """Raise NotImplementedError."""
        raise NotImplementedError

    def listBuildRPMs(self, *args, **kw):
        """Raise NotImplementedError."""
        raise NotImplementedError

    def listTags(self, *args, **kw):
        """Raise NotImplementedError."""
        raise NotImplementedError

    def listTagged(self, *args, **kw):
        """Raise NotImplementedError."""
        raise NotImplementedError

    def taskFinished(self, *args, **kw):
        """Raise NotImplementedError."""
        raise NotImplementedError

    def tagBuild(self, *args, **kw):
        """Raise NotImplementedError."""
        raise NotImplementedError

    def untagBuild(self, *args, **kw):
        """Raise NotImplementedError."""
        raise NotImplementedError

    def multiCall(self, *args, **kw):
        """Raise NotImplementedError."""
        raise NotImplementedError

    def getTag(self, *args, **kw):
        """Raise NotImplementedError."""
        raise NotImplementedError

    def addTag(self, *args, **kw):
        """Raise NotImplementedError."""
        raise NotImplementedError

    def deleteTag(self, *args, **kw):
        """Raise NotImplementedError."""
        raise NotImplementedError


class DevBuildsys(Buildsystem):
    """A dummy buildsystem instance used during development and testing."""

    __untag__ = []
    __moved__ = []
    __added__ = []
    __tagged__ = {}
    __rpms__ = []
    __tags__ = []

    def __init__(self):
        """Initialize the DevBuildsys."""
        self._multicall = False
        self.multicall_result = []

    @property
    def multicall(self):
        """
        Return the value of self._multicall.

        Returns:
            object: The value of self._multicall.
        """
        return self._multicall

    @multicall.setter
    def multicall(self, value):
        """
        Set the _multicall attribute to the given value.

        Args:
            value (object): The value to set the _multicall attribute to.
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

    def multiCall(self):
        """Emulate Koji's multiCall."""
        result = self.multicall_result
        self.multicall = False
        return result

    def moveBuild(self, from_tag, to_tag, build, *args, **kw):
        """Emulate Koji's moveBuild."""
        if to_tag is None:
            raise RuntimeError('Attempt to tag {} with None.'.format(build))
        log.debug("moveBuild(%s, %s, %s)" % (from_tag, to_tag, build))
        DevBuildsys.__moved__.append((from_tag, to_tag, build))

    def tagBuild(self, tag, build, *args, **kw):
        """Emulate Koji's tagBuild."""
        if tag is None:
            raise RuntimeError('Attempt to tag {} with None.'.format(build))
        log.debug("tagBuild(%s, %s)" % (tag, build))
        DevBuildsys.__added__.append((tag, build))

    def untagBuild(self, tag, build, *args, **kw):
        """Emulate Koji's untagBuild."""
        if tag is None:
            raise RuntimeError('Attempt to untag {} with None.'.format(build))
        log.debug("untagBuild(%s, %s)" % (tag, build))
        DevBuildsys.__untag__.append((tag, build))

    def ssl_login(self, *args, **kw):
        """Emulate Koji's ssl_login."""
        log.debug("ssl_login(%s, %s)" % (args, kw))

    def taskFinished(self, task):
        """Emulate Koji's taskFinished."""
        return True

    def getTaskInfo(self, task):
        """Emulate Koji's getTaskInfo."""
        return {'state': koji.TASK_STATES['CLOSED']}

    def getTaskRequest(self, task_id):
        """Emulate Koji's getTaskRequest."""
        return [
            u'git://pkgs.fedoraproject.org/rpms/bodhi?#2e994ca8b3296e62e8b0aadee1c5c0649559625a',
            'f17-candidate', {}]

    def listPackages(self):
        """Emulate Koji's listPackages."""
        return [
            {'package_id': 2625, 'package_name': 'nethack'},
        ]

    @multicall_enabled
    def getBuild(self, build='TurboGears-1.0.2.2-2.fc17', other=False, testing=False):
        """Emulate Koji's getBuild."""
        theid = 16058
        if other and not testing:
            theid = 16059
        elif other and testing:
            theid = 16060
        data = {'build_id': 16058,
                'completion_time': '2007-08-24 23:26:10.890319',
                'completion_ts': 1187997970,
                'creation_event_id': 151517,
                'creation_time': '2007-08-24 19:38:29.422344',
                'extra': None,
                'epoch': None,
                'id': theid,
                'owner_id': 388,
                'owner_name': 'lmacken',
                'package_id': 8,
                'state': 1,
                'tag_id': 19,
                'task_id': 127621}

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

        return data

    def listBuildRPMs(self, id, *args, **kw):
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

    def listTags(self, build, *args, **kw):
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
    def listTagged(self, tag, *args, **kw):
        """List updates tagged with teh given tag."""
        builds = []
        for build in [self.getBuild(),
                      self.getBuild(other=True),
                      self.getBuild(other=True, testing=True)]:
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

    def getLatestBuilds(self, *args, **kw):
        """
        Return a list of the output from self.getBuild().

        Returns:
            list: A list of the latest builds from getBuild().
        """
        return [self.getBuild()]

    def getTag(self, taginfo, **kw):
        """
        Retrieve the given tag from koji.

        Args:
            taginfo (int or basestring): The tag you want info about.
            strict (bool): If True, raise an Exception if epel tags are queried. Defaults to False.
        Returns:
            dict or None: A dictionary of tag information, or None if epel is requested and strict
                is False.
        Raises:
            koji.GenericError: If strict is True and epel is requested.
        """
        for nr in self.__tags__:
            if taginfo == self.__tags__[nr][0]:
                toreturn = self.__tags__[nr][1]
                toreturn['id'] = nr
                return toreturn

        if isinstance(taginfo, int):
            taginfo = "f%d" % taginfo

        if taginfo.startswith("epel"):
            if kw.get("strict", False):
                raise koji.GenericError("Invalid tagInfo: '%s'" % taginfo)

            else:
                return None

        return {'maven_support': False, 'locked': False, 'name': taginfo,
                'perm': None, 'id': 246, 'arches': None,
                'maven_include_all': False, 'perm_id': None}

    def addTag(self, tag, **opts):
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

    def deleteTag(self, tagid):
        """Emulate tag deletion."""
        del self.__tags__[tagid]

    def getRPMHeaders(self, rpmID, headers):
        """
        Return headers for the given RPM.

        Args:
            rpmID (basestring): The RPM you want headers for.
            headers (object): Unused.
        Returns:
            dict: A dictionary of RPM headers.
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
            return headers


def koji_login(config, authenticate):
    """
    Login to Koji and return the session.

    Args:
        config (bodhi.server.config.BodhiConfig): Bodhi's configuration dictionary.
        authenticate (bool): If True, establish an authenticated client session.
    Returns:
        koji.ClientSession: An authenticated Koji ClientSession that is ready to use.
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


def get_krb_conf(config):
    """
    Return arguments for krb_login.

    Args:
        config (bodhi.server.config.BodhiConfig): Bodhi's configuration dictionary.
    Returns:
        dict: A dictionary containing three keys:
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
        args['ccache'] = ccache
    return args


def get_session():
    """
    Get a new buildsystem instance.

    Returns:
        koji.ClientSession or DevBuildsys: A buildsystem client instance.
    Raises:
        RuntimeError: If the build system has not been initialized. See setup_buildsystem().
    """
    global _buildsystem, _buildsystem_login_lock
    if _buildsystem is None:
        raise RuntimeError('Buildsys needs to be setup')
    with _buildsystem_login_lock:
        return _buildsystem()


def teardown_buildsystem():
    """Tear down the build system."""
    global _buildsystem
    _buildsystem = None
    DevBuildsys.clear()


def setup_buildsystem(settings, authenticate=True):
    """
    Initialize the buildsystem client.

    Args:
        settings (bodhi.server.config.BodhiConfig): Bodhi's config.
        authenticate (bool): If True, establish an authenticated Koji session. Defaults to True.
    Raises:
        ValueError: If the buildsystem is configured to an invalid value.
    """
    global _buildsystem, _koji_hub, _buildsystem_login_lock
    if _buildsystem:
        return

    _buildsystem_login_lock = Lock()
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


def wait_for_tasks(tasks, session=None, sleep=300):
    """
    Wait for a list of koji tasks to complete.

    Args:
        tasks (list): The return value of Koji's multiCall().
        session (koji.ClientSession or None): A Koji client session to use. If not provided, the
            function will acquire its own session.
        sleep (int): How long to sleep between polls on Koji when waiting for tasks to complete.
    Returns:
        list: A list of failed tasks. An empty list indicates that all tasks completed successfully.
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
