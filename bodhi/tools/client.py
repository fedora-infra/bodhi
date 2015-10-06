#!/usr/bin/python2 -tt
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# Copyright 2007-2014  Red Hat, Inc
# Authors: Luke Macken <lmacken@redhat.com>

__version__ = '0.9.14'
__description__ = 'Command line tool for interacting with Bodhi'

import os
import sys
import logging
import urllib2
import subprocess

from getpass import getpass, getuser
from optparse import OptionParser
from datetime import datetime, timedelta

from kitchen.text.converters import to_bytes
from fedora.client import AuthError, ServerError
from fedora.client.bodhi import BodhiClient

try:
    from turbogears import config
    from bodhi.util import load_config
    load_config()
    BODHI_URL = config.get('bodhi_url', 'https://admin.fedoraproject.org/updates/')
except:
    BODHI_URL = 'https://admin.fedoraproject.org/updates/'

update_types = ['bugfix', 'security', 'enhancement', 'newpackage']
update_requests = ['stable', 'testing', 'obsolete', 'unpush']

log = logging.getLogger(__name__)

def get_default_user():
    return os.getenv('FAS_USERNAME', getuser())

def get_parser():
    usage = "usage: %prog [options] [build...|package]"
    parser = OptionParser(usage, description=__description__,
                          version=__version__)

    ## Actions
    parser.add_option("-n", "--new", action="store_true", dest="new",
                      help="Submit a new update")
    parser.add_option("-e", "--edit", action="store_true", dest="edit",
                      help="Edit an existing update")
    parser.add_option("-M", "--masher", action="store_true", dest="masher",
                      help="Display the status of the Masher (releng only)")
    parser.add_option("-P", "--push", action="store_true", dest="push",
                      help="Display and push any pending updates (releng only)")
    parser.add_option("--push-type", action="append", type="string",
                      dest="push_type",
                      help="Types of updates to push (releng only)")
    parser.add_option("--push-release", action="append", type="string",
                      dest="push_release",
                      help="Types of updates to push (releng only)")
    parser.add_option("--push-request", action="append", type="string",
                      dest="push_request",
                      help="Requests of updates to push (stable or testing) (releng only)")
    parser.add_option("--push-build", action="append", type="string",
                      dest="push_build", help="Push a specific builds (releng only)")
    parser.add_option("--resume-push", action="store_true", dest="resume_push",
                      help="Resume an unfinished push (releng only)")
    parser.add_option("-d", "--delete", action="store_true", dest="delete",
                      help="Delete an update")
    parser.add_option("", "--file", action="store", type="string",
                      dest="input_file", help="Get update details from a file")
    parser.add_option("-m", "--mine", action="store_true", dest="mine",
                      help="Display a list of your updates")
    parser.add_option("-C", "--candidates", action="store_true",
                      help="Display a list of your update candidates",
                      dest="candidates")
    parser.add_option("-T", "--testable", action="store_true",
                      help="Display a list of installed updates that you "
                           "could test and provide feedback for")
    parser.add_option("-c", "--comment", action="store", dest="comment",
                      help="Comment on an update")
    parser.add_option("-k", "--karma", action="store", dest="karma",
                      metavar="[+1|-1]", default=0,
                      help="Give karma to a specific update (default: 0)")
    parser.add_option("-R", "--request", action="store", dest="request",
                      metavar="STATE", help="Request that an action be "
                      "performed on an update [testing|stable|unpush|obsolete]")
    parser.add_option("-D", "--download", action="store", dest="download",
                      metavar="UPDATE", help="Download an update")

    parser.add_option("", "--critpath", action="store_true",
                      help="Display a list of pending critical path updates",
                      dest="critpath")
    parser.add_option("", "--untested", action="store_true",
                      help="Display a list of untested critical path updates",
                      dest="untested", default=False)

    ## Buildroot Override Options
    parser.add_option("-o", "--buildroot-override", action="store",
                      help="Submit a build as a buildroot override",
                      dest="override", metavar="BUILD")
    parser.add_option("--duration", action="store",
                      help="Duration of the buildroot override",
                      dest="duration", metavar="DAYS",
                      default=3)
    parser.add_option("-O", "--list-overrides", action="store_true",
                      help="List all buildroot overrides",
                      dest="list_overrides")
    parser.add_option("--my-overrides", action="store_true",
                      help="List all of your specific buildroot overrides",
                      dest="my_overrides", default=False)
    parser.add_option("-E", "--expire-override", action="store",
                      help="Expire a buildroot override",
                      dest="expire_override", metavar="BUILD")
    parser.add_option("--show-expired", action="store_true",
                      help="Show expired buildroot overrides",
                      dest="show_expired", default=False)
    parser.add_option("--edit-override", action="store",
                      help="Edit override duration or notes",
                      dest="edit_override", default=None,
                      metavar="BUILD")

    ## Details
    parser.add_option("-s", "--status", action="store", type="string",
                      dest="status", help="List [pending|testing|stable|"
                      "obsolete] updates")
    parser.add_option("-b", "--bugs", action="store", type="string",
                      dest="bugs", help="Specify any number of Bugzilla IDs "
                      "(--bugs=1234,5678)", default="")
    parser.add_option("-r", "--release", action="store", type="string",
                      dest="release", help="Specify a release [F12|F13|F14] (optional)")
    parser.add_option("-N", "--notes", action="store", type="string",
                      dest="notes", help="Update notes", default="")
    parser.add_option("-t", "--type", action="store", type="string",
                      help="Update type [%s]" % '|'.join(update_types),
                      dest="type_", metavar="TYPE")
    parser.add_option("-u", "--username", action="store", type="string",
                      dest="username", default=get_default_user(),
                      help="Login username for bodhi")
    parser.add_option("-L", "--latest", action="store", type="string",
                      dest="latest", help="List the latest builds of a "
                      "specific package across all releases")
    parser.add_option("", "--disable-autokarma", action="store_true",
                      dest="disable_autokarma", help="Disable karma automatism",
                      default=False)
    parser.add_option("-S", "--stablekarma", action="store", type="int",
                      dest="stablekarma", help="Stable karma threshold",
                      default=3)
    parser.add_option("-U", "--unstablekarma", action="store", type="int",
                      dest="unstablekarma", help="Unstable karma threshold",
                      default=-3)
    parser.add_option("-B", "--close-bugs", action="store_true",
                      dest="close_bugs", help="Automatically comment on RHBZ",
                      default=False)

    ## Output
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
                      help="Show debugging messages")
    parser.add_option("-l", "--limit", action="store", type="int", dest="limit",
                      default=60, help="Maximum number of updates to return "
                      "(default: 60)")

    ## Expert options
    parser.add_option("", "--bodhi-url", type="string",
            help="Bodhi url to use for testing purposes (default: %s)" %
            BODHI_URL, dest="bodhi_url", default=BODHI_URL)
    return parser

def setup_logger(verbose):
    global log
    sh = logging.StreamHandler()
    level = verbose and logging.DEBUG or logging.INFO
    log.setLevel(level)
    sh.setLevel(level)
    format = logging.Formatter("%(message)s")
    sh.setFormatter(format)
    log.addHandler(sh)

def main():
    parser = get_parser()
    opts, args = parser.parse_args()
    setup_logger(opts.verbose)

    bodhi = BodhiClient(opts.bodhi_url, username=opts.username, debug=opts.verbose)
    bodhi.timeout = 300

    def verify_args(args):
        if not args and len(args) != 1:
            log.error("Please specifiy a comma-separated list of builds")
            sys.exit(-1)

    override_notes = None

    while True:
        try:
            if opts.new:
                # Note: All options are ignored if you're passing input from a file.
                if opts.input_file:
                    updates = bodhi.parse_file(input_file=opts.input_file)
                    for update_args in updates:
                        if not update_args['type_']:
                            log.error("Error: No update type specified (ie: "
                                      "type=bugfix), skipping.")
                            continue
                        if update_args['type_'] not in update_types:
                            log.error('Error: Invalid update type %r. Must be one of %r'
                                      % (update_args['type_'], update_types))
                            continue
                        if update_args['request'] not in update_requests:
                            log.error('Error: Invalid update request %r. Must be one of %r'
                                      % (update_args['request'], update_requests))
                            continue
                        log.info("Creating a new update for %s" %
                                 update_args['builds'])
                        data = bodhi.save(**update_args)
                        if data.get('tg_flash'):
                            log.info(data['tg_flash'])
                        if 'updates' in data:
                            for update in data['updates']:
                                print(bodhi.update_str(update).encode("UTF-8"))
                        elif 'title' in data:
                            print(bodhi.update_str(data).encode("UTF-8"))

                else:
                    builds = ",".join(args)
                    extra_args = {
                        'builds': builds,
                        'type_': opts.type_,
                        'bugs': opts.bugs,
                        'notes': opts.notes,
                        'request': opts.request or 'testing',
                        'stable_karma': opts.stablekarma,
                        'unstable_karma': opts.unstablekarma,
                        'autokarma': not opts.disable_autokarma,
                        'close_bugs': opts.close_bugs,
                    }
                    if not extra_args['type_']:
                        log.error("Error: No update type specified (ie: -t bugfix)")
                        sys.exit(-1)
                    log.info("Creating a new update for %s" % builds)
                    data = bodhi.save(**extra_args)
                    if data.get('tg_flash'):
                        log.info(data['tg_flash'])
                    if 'updates' in data:
                        for update in data['updates']:
                            print(bodhi.update_str(update).encode("UTF-8"))
                    elif 'title' in data:
                        print(bodhi.update_str(data).encode("UTF-8"))

            elif opts.edit:
                verify_args(args)
                log.info("Editing update for %s" % args[0])
                data = bodhi.save(builds=args[0], type_=opts.type_,
                                  bugs=opts.bugs, notes=opts.notes,
                                  request=opts.request)
                log.info(data['tg_flash'])
                if 'update' in data:
                    print(bodhi.update_str(data['update']).encode("UTF-8"))

            elif opts.request:
                verify_args(args)
                data = bodhi.request(update=args[0], request=opts.request)
                log.info(data['tg_flash'])
                if 'update' in data:
                    print(bodhi.update_str(data['update']).encode("UTF-8"))

            elif opts.delete:
                verify_args(args)
                data = bodhi.delete(update=args[0])
                log.info(data['tg_flash'])

            elif opts.push:
                data = bodhi.push()
                if not data:
                    log.error("The masher did not return anything :(")
                    raise AuthError
                if not data.get('updates', None):
                    log.info(data.get('message', 'Unknown masher reply'))
                    raise AuthError
                if opts.push_type:
                    fupdates = []
                    for ptype in opts.push_type:
                        fdata = filter(lambda x: x['type'] == ptype, data['updates'])
                        fupdates += fdata
                    data['updates'] = fupdates
                if opts.push_request:
                    fupdates = []
                    for req in opts.push_request:
                        fdata = filter(lambda x: x['request'] == req,
                                       data['updates'])
                        fupdates += fdata
                    data['updates'] = fupdates
                if opts.push_release:
                    fupdates = []
                    for prel in opts.push_release:
                        fdata = filter(lambda x: x['release']['name'] == prel,
                                       data['updates'])
                        fupdates += fdata
                    data['updates'] = fupdates
                if opts.push_build:
                    data['updates'] = filter(lambda x: x['title'].split(',')[0] in
                                             opts.push_build, data['updates'])

                for status in ('testing', 'stable', 'obsolete'):
                    updates = filter(lambda x: x['request'] == status,
                                     data['updates'])

                    releases = {}
                    for update in updates:
                        releases.setdefault(update['release']['name'], []) \
                                .append(update)

                    if len(updates):
                        log.info("\n" + status.title() + "\n========")
                        for release in releases:
                            f = open(status.title() + '-' + release, 'w')
                            log.info(release)
                            for update in releases[release]:
                                log.info("%s" % update['title'])
                                s = "%s" % update['title']
                                s = s.replace(',', '\n')
                                f.write(s + "\n")
                            log.info('')
                            f.write('')
                            f.close()

                log.info("[ %d Pending Requests ]" % len(data['updates']))

                ## Confirm that we actually want to push these updates
                sys.stdout.write("\nPush these updates? [n]")
                sys.stdout.flush()
                yes = sys.stdin.readline().strip()
                if yes.lower() in ('y', 'yes'):
                    log.info("Pushing!")
                    params = {'updates': [update['title'] for update in data['updates']]}
                    if opts.resume_push:
                        params['resume'] = True
                    data = bodhi.send_request('admin/mash', auth=True, req_params=params)
                    log.info(data['tg_flash'])

            elif opts.masher:
                data = bodhi.masher()
                log.info(data['masher_str'])

            elif opts.testable:
                for update in bodhi.testable():
                    # Allow for some basic filtering of installed updates
                    if opts.critpath:
                        if not update['critpath']:
                            continue
                    if opts.type_:
                        if not update['type'] == opts.type_:
                            continue
                    print(bodhi.update_str(update, minimal=opts.verbose).encode("UTF-8"))

            elif opts.candidates:
                for build in bodhi.candidates():
                    log.info("%-40s %-20s" % (build['nvr'], build['tag_name']))

            elif opts.comment or opts.karma:
                if not len(args) or not args[0]:
                    log.error("Please specify an update to comment on")
                    sys.exit(-1)
                data = bodhi.comment(update=args[0], comment=opts.comment,
                                     karma=opts.karma)
                if data['tg_flash']:
                    log.info(data['tg_flash'])
                if 'update' in data:
                    print(bodhi.update_str(data['update']).encode("UTF-8"))

            elif opts.latest:
                data = bodhi.latest_builds(package=opts.latest)
                if 'tg_flash' in data:
                    if data['tg_flash']:
                        log.info(data['tg_flash'])
                    del(data['tg_flash'])
                data = data.items()
                data.sort(cmp=lambda x, y: cmp(x[0].replace('dist-', '').split('-')[0],
                                               y[0].replace('dist-', '').split('-')[0]))
                for dist, build in data:
                    print('%26s  %s' % (dist, build))

            elif opts.critpath:
                log.info("Getting a list of critical path updates...")
                data = bodhi.send_request('critpath', req_params={
                    'untested': opts.untested,
                    'release': opts.release,
                    })
                if data['tg_flash']:
                    log.info(data['tg_flash'])
                for update in data['updates']:
                    print(bodhi.update_str(update, minimal=not opts.verbose).encode("UTF-8"))
                log.info("%d pending critical path updates found" % (
                    len(data['updates'])))

            elif opts.mine and not args:
                data = bodhi.query(mine=opts.mine)
                for update in data['updates']:
                    print(bodhi.update_str(update, minimal=True).encode("UTF-8"))
                log.debug(data)
                log.info(data['title'])

            ## Buildroot Overrides commands
            elif opts.override or opts.edit_override:
                controller = 'override/save'
                if opts.edit_override:
                    controller = 'override/save_edit_cli'
                    builds = opts.edit_override
                else:
                    builds = opts.override
                expiration = None
                if opts.duration:
                    expiration = (datetime.utcnow() +
                        timedelta(days=int(opts.duration))).strftime('%m/%d/%Y')
                if opts.notes:
                    override_notes = opts.notes
                if not override_notes and not opts.edit_override:
                    override_notes = raw_input('Notes: ').strip()
                data = bodhi.send_request(controller, req_params={
                    'builds': builds,
                    'notes': override_notes,
                    'expiration': expiration,
                    }, auth=True)
                if data.get('tg_flash'):
                    log.info(data['tg_flash'])
                else:
                    log.info("No data returned from bodhi?")
            elif opts.expire_override:
                data = bodhi.send_request('override/expire', req_params={
                    'build': opts.expire_override,
                    }, auth=True)
                if data.get('tg_flash'):
                    log.info(data['tg_flash'])
                else:
                    log.info("No data returned from bodhi?")
            elif opts.list_overrides or opts.my_overrides:
                data = bodhi.send_request('override/list', req_params={
                    'mine': opts.my_overrides,
                    'release': opts.release,
                    'show_expired': opts.show_expired,
                    }, auth=True)
                print data['title'] + '\n' + '=' * len(data['title']) + '\n'
                for override in data['overrides']:
                    print "[ %s ]" % override['build']
                    print " * Notes: %s" % override['notes']
                    print " * Submitter: %s" % override['submitter']
                    print " * Submitted: %s" % override['date_submitted']
                    if override['expiration']:
                        print " * Expiration: %s" % override['expiration']
                    if override['date_expired']:
                        print " * Expired: %s" % override['date_expired']
                    print

            ## Query updates
            elif opts.status or opts.bugs or opts.release or opts.type_ or \
                 opts.mine or args:
                def print_query(data):
                    if 'tg_flash' in data and data['tg_flash']:
                        log.error(data['tg_flash'])
                        sys.exit(-1)
                    if data['num_items'] > 1:
                        for update in data['updates']:
                            print(bodhi.update_str(update, minimal=True).encode("UTF-8"))
                        log.info("%d updates found (%d shown)" % (
                            data['num_items'], len(data['updates'])))
                    else:
                        for update in data['updates']:
                            print(bodhi.update_str(update).encode("UTF-8"))
                if args:
                    for arg in args:
                        data = bodhi.query(package=arg, release=opts.release,
                                           status=opts.status, type_=opts.type_,
                                           bugs=opts.bugs, request=opts.request,
                                           mine=opts.mine, limit=opts.limit)
                        print_query(data)
                else:
                    data = bodhi.query(release=opts.release, status=opts.status,
                                       type_=opts.type_, bugs=opts.bugs,
                                       request=opts.request, mine=opts.mine,
                                       limit=opts.limit)
                    print_query(data)

            elif opts.download:
                if opts.download.startswith('https://') or \
                   opts.download.startswith('http://'):
                    opts.download = opts.download.split('/')[-1]
                data = bodhi.query(release=opts.release, status=opts.status,
                                   type_=opts.type_, bugs=opts.bugs,
                                   request=opts.request, mine=opts.mine,
                                   limit=opts.limit, package=opts.download)
                if len(data['updates']) > 1:
                    log.info("%d possible updates were found" %
                             len(data['updates']))
                    for update in data['updates']:
                        print(bodhi.update_str(update, minimal=True).encode("UTF-8"))
                else:
                    update = data['updates'][0]
                    log.info("Downloading %s..." % update['title'])
                    p = subprocess.Popen('uname -m', shell=True,
                                         stdout=subprocess.PIPE)
                    arch = p.communicate()[0].strip()
                    for build in update['builds']:
                        subprocess.call('koji download-build --arch=%s '
                                        '--arch=noarch%s %s' % (arch,
                                            arch == 'i686' and ' --arch=i386 --arch=i586'
                                            or '', build['nvr']),
                                        shell=True)

            else:
                parser.print_help()
            break

        except AuthError, e:
            log.debug('Caught AuthError: %s' % to_bytes(e))
            bodhi.password = getpass('Password for %s: ' % opts.username)
        except ServerError, e:
            log.exception(e)
            #log.error(e.message)
            sys.exit(-1)
        except urllib2.URLError, e:
            log.error(e)
            sys.exit(-1)


if __name__ == '__main__':
    main()
