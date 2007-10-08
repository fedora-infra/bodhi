#!/usr/bin/python -tt
# $Id: $
#
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
# Copyright 2007, Red Hat, Inc
# Authors: Luke Macken <lmacken@redhat.com>

import re
import sys
import os
import logging

from getpass import getpass, getuser
from optparse import OptionParser

from fedora.tg.client import BaseClient, AuthError
#sys.path.append('/home/lmacken/code/python-fedora-devel/fedora/tg')
#from client import BaseClient, AuthError, ServerError

log = logging.getLogger(__name__)

__version__ = '$Revision: $'[11:-2]
__description__ = 'Command line tool for interacting with Bodhi'

BODHI_URL = 'http://localhost:8084/updates/'


class BodhiClient(BaseClient):
    """
        A command-line client to interact with Bodhi.
    """

    def new(self, opts):
        if opts.input_file:
            self._parse_file(opts)
        log.info("Creating new update for %s" % opts.new)
        input = {
                'builds'  : opts.new,
                'release' : opts.release,
                'type'    : opts.type,
                'bugs'    : opts.bugs,
                'cves'    : opts.cves,
                'notes'   : opts.notes
        }
        data = self.send_request('save', auth=True, input=input)
        log.info(data['tg_flash'])
        if data.has_key('update'):
            log.info(data['update'])

    def list(self, opts):
        args = { 'tg_paginate_limit' : opts.limit }
        for arg in ('release', 'status', 'type', 'bugs', 'cves'):
            if getattr(opts, arg):
                args[arg] = getattr(opts, arg)
        data = self.send_request('list', **args)
        if data.has_key('tg_flash') and data['tg_flash']:
            log.error(data['tg_flash'])
            sys.exit(-1)
        for update in data['updates']:
            log.info(update + '\n')
        log.info("%d updates found (%d shown)" % (data['num_items'],opts.limit))

    def delete(self, opts):
        data = self.send_request('delete', input={'update':opts.delete}, auth=True)
        log.info(data['tg_flash'])

    def push_to_testing(self, opts):
        data = self.send_request('push', nvr=opts.testing, auth=True)
        log.info(data['tg_flash'])
        if data.has_key('update'):
            log.info(data['update'])

    def push_to_stable(self, opts):
        data = self.send_request('move', nvr=opts.stable, auth=True)
        log.info(data['tg_flash'])

    def masher(self, opts):
        data = self.send_request('admin/masher', auth=True)
        log.info(data['masher_str'])

    def push(self, opts):
        data = self.send_request('admin/push', auth=True)
        log.info("[ %d Pending Requests ]" % len(data['updates']))
        stable = filter(lambda x: x['request'] == 'stable', data['updates'])
        testing = filter(lambda x: x['request'] == 'testing', data['updates'])
        obsolete = filter(lambda x: x['request'] == 'obsolete', data['updates'])
        for title, updates in (('Testing', testing),
                               ('Stable', stable),
                               ('Obsolete', obsolete)):
            if len(updates):
                log.info("\n" + title + "\n========")
                for update in updates:
                    log.info("%s" % update['title'])

        ## Confirm that we actually want to push these updates
        sys.stdout.write("\nAre you sure you want to push these updates? ")
        sys.stdout.flush()
        yes = sys.stdin.readline().strip()
        if yes in ('y', 'yes'):
            log.info("Pushing!")
            self.send_request('admin/push/mash',
                              updates=[u['title'] for u in data['updates']],
                              auth=True)

    def _split(self,var,delim):
        if var:
            return var.split(delim)
        else:
            return []

    def _parse_file(self,opts):
        regex = re.compile(r'^(BUG|bug|TYPE|type|CVE|cve)=(.*$)')
        types = {'S':'security','B':'bugfix','E':'enhancement'}
        notes = self._split(opts.notes,'\n')
        bugs = self._split(opts.bugs,',')
        cves = self._split(opts.cves,',')
        print "Reading from %s " % opts.input_file
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
    usage = "usage: %prog [options]"
    parser = OptionParser(usage, description=__description__)

    ## Actions
    parser.add_option("-n", "--new", action="store", type="string", dest="new",
                      help="Add a new update to the system (--new=foo-1.2-3,"
                           "bar-4.5-6)")
    parser.add_option("-m", "--masher", action="store_true", dest="masher",
                      help="Display the status of the Masher")
    parser.add_option("-p", "--push", action="store_true", dest="push",
                      help="Display and push any pending updates")

    ## Details
    parser.add_option("-s", "--status", action="store", type="string",
                      dest="status", help="List [pending|testing|stable|obsolete] updates")
    parser.add_option("-b", "--bugs", action="store", type="string",
                      dest="bugs", help="Associate bugs with an update "
                                        "(--bugs=1234,5678)", default="")
    parser.add_option("-c", "--cves", action="store", type="string",
                      dest="cves", help="A list of comma-separated CVE IDs",
                      default="")
    parser.add_option("-r", "--release", action="store", type="string",
                      dest="release", help="Release (default: F7)",
                      default="F7")
    parser.add_option("-N", "--notes", action="store", type="string",
                      dest="notes", help="Update notes", default="")
    parser.add_option("-t", "--type", action="store", type="string",
                      dest="type",
                      help="Update type [bugfix|security|enhancement] "
                           "(default: bugfix)")
    parser.add_option("", "--file", action="store", type="string",
                      dest="input_file",
                      help="Get Bugs,CVES,Notes from a file")
    parser.add_option("-u", "--username", action="store", type="string",
                      dest="username", default=getuser(),
                      help="Fedora username")
    parser.add_option("-S", "--stable", action="store", type="string",
                      dest="stable", metavar="UPDATE",
                      help="Mark an update for push to stable")
    parser.add_option("-T", "--testing", action="store", type="string",
                      dest="testing", metavar="UPDATE",
                      help="Mark an update for push to testing")
    parser.add_option("-d", "--delete", action="store", type="string",
                      dest="delete", help="Delete an update",
                      metavar="UPDATE")

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

    bodhi = BodhiClient(BODHI_URL, opts.username, None, debug=opts.verbose)

    while True:
        try:
            if opts.new:
                bodhi.new(opts)
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
            else:
                parser.print_help()
            break
        except AuthError:
            bodhi.password = getpass('Password for %s: ' % opts.username)
        except ServerError, e:
            log.error(e.message)
            sys.exit(-1)
