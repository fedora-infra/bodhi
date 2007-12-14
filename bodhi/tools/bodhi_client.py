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

import re
import sys
import koji
import logging
import urllib2

from yum import YumBase
from os.path import join, expanduser, exists
from getpass import getpass, getuser
from optparse import OptionParser
from ConfigParser import ConfigParser

from fedora.tg.client import BaseClient, AuthError, ServerError

__version__ = '$Revision: $'[11:-2]
__description__ = 'Command line tool for interacting with Bodhi'

BODHI_URL = 'https://admin.fedoraproject.org/updates/'
log = logging.getLogger(__name__)

class BodhiClient(BaseClient):

    def new(self, builds, opts):
        log.info("Creating new update for %s" % builds)
        params = {
                'builds'  : builds,
                'release' : opts.release.upper(),
                'type'    : opts.type,
                'bugs'    : opts.bugs,
                'notes'   : opts.notes
        }
        if hasattr(opts, 'request') and getattr(opts, 'request'):
            params['request'] = opts.request
        data = self.send_request('save', auth=True, input=params)
        log.info(data['tg_flash'])
        if data.has_key('update'):
            log.info(data['update'])

    def edit(self, builds, opts):
        log.info("Editing update for %s" % builds)
        params = {
                'builds'  : builds,
                'edited'  : builds,
                'release' : opts.release.upper(),
                'type'    : opts.type,
                'bugs'    : opts.bugs,
                'notes'   : opts.notes
        }
        if hasattr(opts, 'request') and getattr(opts, 'request'):
            params['request'] = opts.request
        data = self.send_request('save', auth=True, input=params)
        log.info(data['tg_flash'])
        if data.has_key('update'):
            log.info(data['update'])

    def list(self, opts, package=None, showcount=True):
        args = { 'tg_paginate_limit' : opts.limit }
        for arg in ('release', 'status', 'type', 'bugs', 'request'):
            if getattr(opts, arg):
                args[arg] = getattr(opts, arg)
        if package:
            args['package' ] = package[0]
        data = self.send_request('list', input=args)
        if data.has_key('tg_flash') and data['tg_flash']:
            log.error(data['tg_flash'])
            sys.exit(-1)
        for update in data['updates']:
            print update
        if showcount:
            log.info("%d updates found (%d shown)" % (data['num_items'],
                                                      len(data['updates'])))

    def delete(self, update):
        params = { 'update' : update }
        data = self.send_request('delete', input=params, auth=True)
        log.info(data['tg_flash'])

    def __koji_session(self):
        config = ConfigParser()
        if exists(join(expanduser('~'), '.koji', 'config')):
            config.readfp(open(join(expanduser('~'), '.koji', 'config')))
        else:
            config.readfp(open('/etc/koji.conf'))
        cert = expanduser(config.get('koji', 'cert'))
        ca = expanduser(config.get('koji', 'ca'))
        serverca = expanduser(config.get('koji', 'serverca'))
        session = koji.ClientSession(config.get('koji', 'server'))
        session.ssl_login(cert=cert, ca=ca, serverca=serverca)
        return session

    koji_session = property(fget=__koji_session)

    def candidates(self, opts):
        """
        Display a list of candidate builds which could potentially be pushed
        as updates.  This is a very expensive operation.
        """
        data = self.send_request("dist_tags")
        for tag in [tag + '-updates-candidate' for tag in data['tags']]:
            for build in self.koji_session.listTagged(tag, latest=True):
                if build['owner_name'] == opts.username:
                    print "%-40s %-20s" % (build['nvr'], build['tag_name'])

    def testable(self, opts):
        """
        Display a list of installed updates that you have yet to test
        and provide feedback for.
        """
        fedora = file('/etc/fedora-release').readlines()[0].split()[2]
        if fedora == '7': fedora = 'c7'
        tag = 'dist-f%s-updates-testing' % fedora
        builds = self.koji_session.listTagged(tag, latest=True)

        yum = YumBase()
        yum.doConfigSetup(init_plugins=False)

        for build in builds:
            pkgs = yum.rpmdb.searchNevra(name=build['name'],
                                         epoch=None,
                                         ver=build['version'],
                                         rel=build['release'],
                                         arch=None)
            if len(pkgs):
                self.list(opts, package=[build['nvr']], showcount=False)

    def comment(self, opts, update):
        params = {
                'text'  : opts.comment,
                'karma' : opts.karma,
                'title' : update
        }
        data = self.send_request('comment', input=params, auth=True)
        if data['tg_flash']:
            log.info(data['tg_flash'])
        if data.has_key('update'):
            log.info(data['update'])

    def request(self, opts, update):
        params = { 'action' : opts.request, 'update' : update }
        data = self.send_request('request', input=params, auth=True)
        log.info(data['tg_flash'])
        if data.has_key('update'):
            log.info(data['update'])

    def masher(self):
        data = self.send_request('admin/masher', auth=True)
        log.info(data['masher_str'])

    def mine(self):
        data = self.send_request('mine', auth=True)
        for update in data['updates']:
           log.info(update + '\n')
        log.info("%d updates found (%d shown)" % (data['num_items'],
                                                  len(data['updates'])))

    def push(self, opts):
        data = self.send_request('admin/push', auth=True)
        log.info("[ %d Pending Requests ]" % len(data['updates']))
        for status in ('testing', 'stable', 'obsolete'):
            updates = filter(lambda x: x['request'] == status, data['updates'])
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
            self.send_request('admin/push/mash', auth=True, input={
                    'updates' : [u['title'] for u in data['updates']] })

    def parse_file(self,opts):
        regex = re.compile(r'^(BUG|bug|TYPE|type|REQUEST|request)=(.*$)')
        types = {'S':'security','B':'bugfix','E':'enhancement'}
        requests = {'T':'testing','S':'stable'}
        def _split(var, delim):
            if var: return var.split(delim)
            else: return []
        notes = _split(opts.notes,'\n')
        bugs = _split(opts.bugs,',')
        log.info("Reading from %s " % opts.input_file)
        if exists(opts.input_file):
            f = open(opts.input_file)
            lines = f.readlines()
            f.close()
            for line in lines:
                if line[0] == ':' or line[0] == '#':
                    continue
                src = regex.search(line)
                if src:
                    cmd,para = tuple(src.groups())
                    cmd = cmd.upper()
                    if cmd == 'BUG':
                        para = [p for p in para.split(' ')]
                        bugs.extend(para)
                    elif cmd == 'TYPE':
                        opts.type = types[para.upper()]
                    elif cmd == 'REQUEST':
                        opts.request = requests[para.upper()]
                else: # This is notes
                    notes.append(line.strip())
        if notes:
            opts.notes = "\r\n".join(notes)
        if bugs:
            opts.bugs = ','.join(bugs)
        log.debug("Type : %s" % opts.type)
        log.debug("Request: %s" % opts.request)
        log.debug('Bugs:\n%s' % opts.bugs)
        log.debug('Notes:\n%s' % opts.notes)

def setup_logger():
    sh = logging.StreamHandler()
    if opts.verbose:
        log.setLevel(logging.DEBUG)
        sh.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)
        sh.setLevel(logging.INFO)
    format = logging.Formatter("%(message)s")
    sh.setFormatter(format)
    log.addHandler(sh)


if __name__ == '__main__':
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
                      default=10, help="Maximum number of updates to return "
                      "(default: 10)")

    (opts, args) = parser.parse_args()
    setup_logger()

    bodhi = BodhiClient(BODHI_URL, opts.username, None)

    def verify_args(args):
        if not args and len(args) != 1:
            log.error("Please specifiy a comma-separated list of builds")
            sys.exit(-1)

    while True:
        try:
            if opts.new:
                verify_args(args)
                if opts.input_file:
                    bodhi.parse_file(opts)
                if not opts.release:
                    log.error("Error: No release specified (ie: -r F8)")
                    sys.exit(-1)
                if not opts.type:
                    log.error("Error: No update type specified (ie: -t bugfix)")
                    sys.exit(-1)
                bodhi.new(args[0], opts)
            elif opts.edit:
                verify_args(args)
                bodhi.edit(args[0], opts)
            elif opts.request:
                verify_args(args)
                bodhi.request(opts, args[0])
            elif opts.delete:
                verify_args(args)
                bodhi.delete(args[0])
            elif opts.mine:
                bodhi.mine()
            elif opts.push:
                bodhi.push(opts)
            elif opts.masher:
                bodhi.masher()
            elif opts.testable:
                bodhi.testable(opts)
            elif opts.candidates:
                bodhi.candidates(opts)
            elif opts.comment or opts.karma:
                if not len(args) or not args[0]:
                    log.error("Please specify an update to comment on")
                    sys.exit(-1)
                bodhi.comment(opts, args[0])
            elif opts.status or opts.bugs or opts.release or opts.type or args:
                bodhi.list(opts, args)
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
