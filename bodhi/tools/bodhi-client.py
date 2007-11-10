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
import os
import logging
import urllib2

from getpass import getpass, getuser
from optparse import OptionParser

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
                'cves'    : opts.cves,
                'notes'   : opts.notes
        }
        data = self.send_request('save', auth=True, input=params)
        log.info(data['tg_flash'])
        if data.has_key('update'):
            log.info(data['update'])

    def list(self, opts, package=None):
        args = { 'tg_paginate_limit' : opts.limit }
        for arg in ('release', 'status', 'type', 'bugs', 'cves'):
            if getattr(opts, arg):
                args[arg] = getattr(opts, arg)
        if package:
            args['package' ] = package[0]
        data = self.send_request('list', input=args)
        if data.has_key('tg_flash') and data['tg_flash']:
            log.error(data['tg_flash'])
            sys.exit(-1)
        for update in data['updates']:
            log.info(update + '\n')
        log.info("%d updates found (%d shown)" % (data['num_items'],
                                                  len(data['updates'])))

    def delete(self, opts):
        params = { 'update' : opts.delete }
        data = self.send_request('delete', input=params, auth=True)
        log.info(data['tg_flash'])

    def obsolete(self, opts):
        params = { 'action' : 'obsolete', 'update' : opts.obsolete }
        data = self.send_request('request', input=params, auth=True)
        log.info(data['tg_flash'])

    def push_to_testing(self, opts):
        params = { 'action' : 'testing', 'update' : opts.testing }
        data = self.send_request('request', input=params, auth=True)
        log.info(data['tg_flash'])
        if data.has_key('update'):
            log.info(data['update'])

    def push_to_stable(self, opts):
        params = { 'action' : 'stable', 'update' : opts.stable }
        data = self.send_request('request', input=params, auth=True)
        log.info(data['tg_flash'])

    def masher(self, opts):
        data = self.send_request('admin/masher', auth=True)
        log.info(data['masher_str'])

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
            self.send_request('admin/push/mash', auth=True,
                              input={'updates':[u['title'] for u in data['updates']]})

    def _split(self,var,delim):
        if var:
            return var.split(delim)
        else:
            return []

    def parse_file(self,opts):
        regex = re.compile(r'^(BUG|bug|TYPE|type|CVE|cve)=(.*$)')
        types = {'S':'security','B':'bugfix','E':'enhancement'}
        notes = self._split(opts.notes,'\n')
        bugs = self._split(opts.bugs,',')
        cves = self._split(opts.cves,',')
        log.info("Reading from %s " % opts.input_file)
        if os.path.exists(opts.input_file):
            f = open(opts.input_file)
            lines = f.readlines()
            f.close()
            for line in lines:
                if line[0] == ':' or line[0] == '#':
                    continue
                src=regex.search(line)
                if src:
                    cmd,para = tuple(src.groups())
                    cmd=cmd.upper()
                    if cmd == 'BUG':
                        para = [p for p in para.split(' ')]
                        bugs.extend(para)
                    elif cmd == 'CVE':
                        para = [p for p in para.split(' ')]
                        cves.extend(para)
                    elif cmd == 'TYPE':
                        opts.type = types[para.upper()]

                else: # This is notes
                    notes.append(line[:-1])
        if notes:
            opts.notes = "\r\n".join(notes)
        if bugs:
            opts.bugs = ','.join(bugs)
        if cves:
            opts.cves = ','.join(cves)
        log.debug("Type : %s" % opts.type)
        log.debug('Bugs:\n%s' % opts.bugs)
        log.debug('CVES:\n%s' % opts.cves)
        log.debug('Notes:\n%s' % opts.notes)

if __name__ == '__main__':
    usage = "usage: %prog [options] [ build | package ]"
    parser = OptionParser(usage, description=__description__,
                          version=__version__)

    ## Actions
    parser.add_option("-n", "--new", action="store_true", dest="new",
                      help="Add a new update to the system")
    parser.add_option("-m", "--masher", action="store_true", dest="masher",
                      help="Display the status of the Masher")
    parser.add_option("-P", "--push", action="store_true", dest="push",
                      help="Display and push any pending updates")
    parser.add_option("-d", "--delete", action="store", type="string",
                      dest="delete", help="Delete an update",
                      metavar="UPDATE")
    parser.add_option("-o", "--obsolete", action="store", type="string",
                      dest="obsolete", help="Mark an update as being obsolete",
                      metavar="UPDATE")
    parser.add_option("", "--file", action="store", type="string",
                      dest="input_file", help="Get Bugs,CVES,Notes from a file")
    parser.add_option("-S", "--stable", action="store", type="string",
                      dest="stable", metavar="UPDATE",
                      help="Mark an update for push to stable")
    parser.add_option("-T", "--testing", action="store", type="string",
                      dest="testing", metavar="UPDATE",
                      help="Mark an update for push to testing")

    ## Details
    parser.add_option("-s", "--status", action="store", type="string",
                      dest="status", help="List [pending|testing|stable|"
                      "obsolete] updates")
    parser.add_option("-b", "--bugs", action="store", type="string",
                      dest="bugs", help="Associate bugs with an update "
                      "(--bugs=1234,5678)", default="")
    parser.add_option("-c", "--cves", action="store", type="string",
                      dest="cves", help="A list of comma-separated CVE IDs",
                      default="")
    parser.add_option("-r", "--release", action="store", type="string",
                      dest="release", help="Release [F7|F8]")
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

    # Setup the logger
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

    bodhi = BodhiClient(BODHI_URL, opts.username, None)

    while True:
        try:
            if opts.new:
                if not args and len(args) != 1:
                    log.error("Please specifiy a comma-separated list of builds")
                    sys.exit(-1)
                if opts.input_file:
                    bodhi.parse_file(opts)
                if not opts.release:
                    log.error("Error: No release specified (ie: -r F8)")
                    sys.exit(-1)
                if not opts.type:
                    log.error("Error: No update type specified (ie: -t bugfix)")
                    sys.exit(-1)
                bodhi.new(args[0], opts)
            elif opts.testing:
                bodhi.push_to_testing(opts)
            elif opts.stable:
                bodhi.push_to_stable(opts)
            elif opts.masher:
                bodhi.masher(opts)
            elif opts.push:
                bodhi.push(opts)
            elif opts.delete:
                bodhi.delete(opts)
            elif opts.obsolete:
                bodhi.obsolete(opts)
            elif opts.status or opts.bugs or opts.cves or \
                 opts.release or opts.type or args:
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
