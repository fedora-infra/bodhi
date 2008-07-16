#!/usr/bin/python -tt
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
# Copyright 2007  Red Hat, Inc
# Authors: Luke Macken <lmacken@redhat.com>

import sys
import logging
import urllib2

from getpass import getpass, getuser
from optparse import OptionParser

from fedora.client import AuthError, ServerError
from fedora.client.bodhi import BodhiClient

__version__ = '0.5.0'
__description__ = 'Command line tool for interacting with Bodhi'

BODHI_URL = 'https://admin.fedoraproject.org/updates/'
log = logging.getLogger(__name__)


def get_parser():
    usage = "usage: %prog [options] [build|package]"
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

    ## Details
    parser.add_option("-s", "--status", action="store", type="string",
                      dest="status", help="List [pending|testing|stable|"
                      "obsolete] updates")
    parser.add_option("-b", "--bugs", action="store", type="string",
                      dest="bugs", help="Specify any number of Bugzilla IDs "
                      "(--bugs=1234,5678)", default="")
    parser.add_option("-r", "--release", action="store", type="string",
                      dest="release", help="Specify a release [F7|F8]")
    parser.add_option("-N", "--notes", action="store", type="string",
                      dest="notes", help="Update notes", default="")
    parser.add_option("-t", "--type", action="store", type="string",
                      help="Update type [bugfix|security|enhancement]",
                      dest="type")
    parser.add_option("-u", "--username", action="store", type="string",
                      dest="username", default=getuser(),
                      help="Login username for bodhi")

    ## Output
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose",
                      help="Show debugging messages")
    parser.add_option("-l", "--limit", action="store", type="int", dest="limit",
                      default=60, help="Maximum number of updates to return "
                      "(default: 10)")

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

    bodhi = BodhiClient(BODHI_URL, username=opts.username, debug=opts.verbose)

    def verify_args(args):
        if not args and len(args) != 1:
            log.error("Please specifiy a comma-separated list of builds")
            sys.exit(-1)

    def validate_auth(data):
        """ Hack, until we properly handle exceptions in our base client """
        if 'message' in data and data['message'] == u'You must provide your credentials before accessing this resource.':
            raise AuthError(data['message'])

    while True:
        try:
            if opts.new:
                verify_args(args)
                extra_args = {
                    'builds': args[0], 'release': opts.release,
                    'type': opts.type, 'bugs': opts.bugs, 'notes': opts.notes,
                    'request': opts.request or 'testing',
                }
                if opts.input_file:
                    extra_args.update(
                            bodhi.parse_file(input_file=opts.input_file))
                if not extra_args['release']:
                    log.error("Error: No release specified (ie: -r F8)")
                    sys.exit(-1)
                if not extra_args['type']:
                    log.error("Error: No update type specified (ie: -t bugfix)")
                    sys.exit(-1)
                log.info("Creating a new update for %s" % args[0])
                data = bodhi.save(**extra_args)
                if data.get('tg_flash'):
                    log.info(data['tg_flash'])
                if 'update' in data:
                    log.info(data['update'])
                else:
                    validate_auth(data)
            elif opts.edit:
                verify_args(args)
                log.info("Editing update for %s" % args[0])
                data = bodhi.save(builds=args[0], release=opts.release, 
                                  type=opts.type, bugs=opts.bugs,
                                  notes=opts.notes, request=opts.request)
                log.info(data['tg_flash'])
                validate_auth(data)
                if data.has_key('update'):
                    log.info(data['update'])
            elif opts.request:
                verify_args(args)
                data = bodhi.request(update=args[0], request=opts.request)
                validate_auth(data)
                log.info(data['tg_flash'])
                if data.has_key('update'):
                    log.info(data['update'])
            elif opts.delete:
                verify_args(args)
                data = bodhi.delete(update=args[0])
                validate_auth(data)
                log.info(data['tg_flash'])
            elif opts.push:
                data = bodhi.push()
                log.info("[ %d Pending Requests ]" % len(data['updates']))
                for status in ('testing', 'stable', 'obsolete'):
                    updates = filter(lambda x: x['request'] == status,
                                     data['updates'])
                    if len(updates):
                        log.info("\n" + status.title() + "\n========")
                        for update in updates:
                            log.info("%s" % update['title'])

                ## Confirm that we actually want to push these updates
                sys.stdout.write("\nPush these updates? [n]")
                sys.stdout.flush()
                yes = sys.stdin.readline().strip()
                if yes.lower() in ('y', 'yes'):
                    log.info("Pushing!")
                    data = bodhi.push_updates([update['title'] for update in
                                               data['updates']])
                    log.info(data['tg_flash'])
            elif opts.masher:
                data = bodhi.masher()
                log.info(data['masher_str'])
            elif opts.testable:
                for update in bodhi.testable():
                    log.info(bodhi.update_str(update))
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
                validate_auth(data)
                if data.has_key('update'):
                    log.info(data['update'])
            elif opts.mine and not args:
                data = bodhi.query(mine=opts.mine)
                for update in data['updates']:
                    log.info(bodhi.update_str(update, minimal=True))
                log.info(data['title'])
            elif opts.status or opts.bugs or opts.release or opts.type or \
                 opts.mine or args:
                def print_query(data):
                    if data.has_key('tg_flash') and data['tg_flash']:
                        log.error(data['tg_flash'])
                        sys.exit(-1)
                    if data['num_items'] > 1:
                        for update in data['updates']:
                            log.info(bodhi.update_str(update, minimal=True))
                    else:
                        for update in data['updates']:
                            log.info(bodhi.update_str(update))
                        log.info("%d updates found (%d shown)" % (
                            data['num_items'], len(data['updates'])))
                if args:
                    for arg in args:
                        data = bodhi.query(package=arg, release=opts.release,
                                           status=opts.status, type=opts.type,
                                           bugs=opts.bugs, request=opts.request,
                                           mine=opts.mine, limit=opts.limit)
                        print_query(data)
                else:
                    data = bodhi.query(release=opts.release, status=opts.status,
                                       type=opts.type, bugs=opts.bugs,
                                       request=opts.request, mine=opts.mine,
                                       limit=opts.limit)
                    print_query(data)
            else:
                parser.print_help()
            break
        except AuthError:
            bodhi.password = getpass('Password for %s: ' % opts.username)
        except ServerError, e:
            log.error(e.message)
            sys.exit(-1)
        except urllib2.URLError, e:
            log.error(e)
            sys.exit(-1)


if __name__ == '__main__':
    main()
