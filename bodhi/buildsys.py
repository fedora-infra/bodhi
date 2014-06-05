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

import time
import atexit
import logging

from os.path import join, expanduser

log = logging.getLogger(__name__)

_buildsystem = None

try:
    import koji
except ImportError:
    log.warn("Could not import 'koji'")

# Cached koji session info
_koji_session = None

# URL of the koji hub
_koji_hub = None


class Buildsystem:
    """
    The parent for our buildsystem.  Not only does this help us keep track of
    the functionality that we expect from our buildsystem, but it also alows
    us to create a development subclass of this object to use during
    development so we don't alter any production data.
    """
    def getBuild(self, *args, **kw):
        raise NotImplementedError

    def getLatestBuilds(self, *args, **kw):
        raise NotImplementedError

    def moveBuild(self, *args, **kw):
        raise NotImplementedError

    def ssl_login(self, *args, **kw):
        raise NotImplementedError

    def listBuildRPMs(self, *args, **kw):
        raise NotImplementedError

    def listTags(self, *args, **kw):
        raise NotImplementedError

    def listTagged(self, *args, **kw):
        raise NotImplementedError

    def taskFinished(self, *args, **kw):
        raise NotImplementedError

    def tagBuild(self, *args, **kw):
        raise NotImplementedError

    def untagBuild(self, *args, **kw):
        raise NotImplementedError

    def multiCall(self, *args, **kw):
        raise NotImplementedError

    def getTag(self, *args, **kw):
        raise NotImplementedError


class DevBuildsys(Buildsystem):
    """
    A dummy buildsystem instance used during development and testing
    """
    __untag__ = []
    __moved__ = []
    __added__ = []
    __tagged__ = {}

    def clear(self):
        DevBuildsys.__untag__ = []
        DevBuildsys.__moved__ = []
        DevBuildsys.__added__ = []
        DevBuildsys.__tagged__ = {}

    def multiCall(self):
        return []

    def moveBuild(self, from_tag, to_tag, build, *args, **kw):
        log.debug("moveBuild(%s, %s, %s)" % (from_tag, to_tag, build))
        DevBuildsys.__moved__.append((from_tag, to_tag, build))

    def tagBuild(self, tag, build, *args, **kw):
        log.debug("tagBuild(%s, %s)" % (tag, build))
        DevBuildsys.__added__.append((tag, build))

    def untagBuild(self, tag, build, *args, **kw):
        log.debug("untagBuild(%s, %s)" % (tag, build))
        DevBuildsys.__untag__.append((tag, build))

    def ssl_login(self, *args, **kw):
        log.debug("ssl_login(%s, %s)" % (args, kw))

    def taskFinished(self, task):
        return True

    def getTaskInfo(self, task):
        return {'state': koji.TASK_STATES['CLOSED']}

    def listPackages(self):
        return [
            {'package_id': 2625, 'package_name': 'nethack'},
        ]

    def getBuild(self, build='TurboGears-1.0.2.2-2.fc7', other=False):
        data = {'build_id': 16058,
                'completion_time': '2007-08-24 23:26:10.890319',
                'creation_event_id': 151517,
                'creation_time': '2007-08-24 19:38:29.422344',
                'epoch': None,
                'id': 16059 if other else 16058,
                'owner_id': 388,
                'owner_name': 'lmacken',
                'package_id': 8,
                'state': 1,
                'tag_id': 19,
                'task_id': 127621}

        name, version, release = build.rsplit("-", 2)
        release_tokens = release.split(".")

        for token in release_tokens:
            if token.startswith("fc"):
                tag = "f%s-updates-testing" % token.replace("fc", "")
                break

            if token.startswith("el"):
                tag = "dist-%sE-epel-testing-candidate" % token.replace("el", "")
                break

        else:
            raise ValueError("Couldn't determine dist for build '%s'" % build)

        if other:
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
        rpms = [{'arch': 'src',
                 'build_id': 6475,
                 'buildroot_id': 1883,
                 'buildtime': 1178868422,
                 'epoch': None,
                 'id': 62330,
                 'name': 'TurboGears',
                 'nvr': 'TurboGears-1.0.2.2-2.fc7',
                 'payloadhash': '6787febe92434a9be2a8f309d0e2014e',
                 'release': '2.fc7',
                 'size': 761742,
                 'version': '1.0.2.2'},
                {'arch': 'noarch',
                 'build_id': 6475,
                 'buildroot_id': 1883,
                 'buildtime': 1178868537,
                 'epoch': None,
                 'id': 62331,
                 'name': 'TurboGears',
                 'nvr': 'TurboGears-1.0.2.2-2.fc7',
                 'payloadhash': 'f3ec9bdce453816f94283a15a47cb952',
                 'release': '2.fc7',
                 'size': 1993385,
                 'version': '1.0.2.2'},
                ]
        if id == 16059:  # for updateinfo.xml tests
            rpms[0]['nvr'] = rpms[1]['nvr'] = 'TurboGears-1.0.2.2-3.fc7'
            rpms[0]['release'] = rpms[1]['release'] = '3.fc7'
        return rpms

    def listTags(self, build, *args, **kw):
        if 'el5' in build:
            result = [{'arches': 'i386 x86_64 ppc ppc64', 'id': 10, 'locked': True,
                     'name': 'dist-5E-epel-testing-candidate', 'perm': None, 'perm_id': None},
                    {'arches': 'i386 x86_64 ppc ppc64', 'id': 10, 'locked': True,
                     'name': 'dist-5E-epel-testing-candidate', 'perm': None, 'perm_id': None},
                    {'arches': 'i386 x86_64 ppc ppc64', 'id': 5, 'locked': True,
                     'name': 'dist-5E-epel', 'perm': None, 'perm_id': None}]
        else:
            release = build.split('.')[-1].replace('fc', 'f')
            result = [{'arches': 'i386 x86_64 ppc ppc64', 'id': 10, 'locked': True,
                     'name': '%s-updates-candidate' % release, 'perm': None, 'perm_id': None},
                    {'arches': 'i386 x86_64 ppc ppc64', 'id': 5, 'locked': True,
                     'name': '%s' % release, 'perm': None, 'perm_id': None},
                    {'arches': 'i386 x86_64 ppc ppc64', 'id': 5, 'locked': True,
                     'name': '%s-updates-testing' % release, 'perm': None, 'perm_id': None}]
        if build in DevBuildsys.__tagged__:
            for tag in DevBuildsys.__tagged__[build]:
                result += [{'name': tag}]
        return result

    def listTagged(self, tag, *args, **kw):
        builds = []
        for build in [self.getBuild(), self.getBuild(other=True)]:
            if build['nvr'] in self.__untag__:
                print('Pruning koji build %s' % build['nvr'])
                continue
            else:
                builds.append(build)
        return builds

    def getLatestBuilds(self, *args, **kw):
        return [self.getBuild()]

    def getTag(self, taginfo, **kw):
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


def koji_login(config, client=None, clientca=None, serverca=None):
    """
    Login to Koji and return the session
    """
    global _koji_hub, _koji_session
    if not client:
        client = config.get('client_cert')
        if not client:
            client = join(expanduser('~'), '.fedora.cert')
    if not clientca:
        clientca = config.get('clientca_cert')
        if not clientca:
            clientca = join(expanduser('~'), '.fedora-upload-ca.cert')
    if not serverca:
        serverca = config.get('serverca_cert')
        if not serverca:
            serverca = join(expanduser('~'), '.fedora-server-ca.cert')

    _koji_hub = config.get('koji_hub')
    koji_client = koji.ClientSession(_koji_hub, {})
    koji_client.ssl_login(client, clientca, serverca)
    _koji_session = koji_client.sinfo
    return _koji_session


def get_session():
    """ Get a new buildsystem instance """
    global _buildsystem
    if not _buildsystem:
        log.warning('No buildsystem configured; assuming testing')
        return DevBuildsys()
    return _buildsystem()


def close_session():
    koji = get_session()
    try:
        koji.logout()
    except Exception, e:
        log.debug('Exception while closing koji session: %s' % e)


def setup_buildsystem(settings):
    global _buildsystem, _koji_session, _koji_hub
    if _buildsystem:
        return
    buildsys = settings.get('buildsystem')
    if buildsys == 'koji':
        log.debug('Using Koji Buildsystem')
        koji_login(config=settings)
        #_buildsystem = lambda: koji.ClientSession(_koji_hub, sinfo=_koji_session)
        _buildsystem = lambda: koji.ClientSession(_koji_hub)
        atexit.register(close_session)
    elif buildsys in ('dev', 'dummy', None):
        log.debug('Using DevBuildsys')
        _buildsystem = DevBuildsys


def wait_for_tasks(tasks, sleep=300):
    """
    Wait for a list of koji tasks to complete.  Return the first task number
    to fail, otherwise zero.
    """
    log.debug("Waiting for %d tasks to complete: %s" % (len(tasks), tasks))
    failed_tasks = []
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
    log.debug("Tasks completed successfully!")
    return failed_tasks
