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
# Authors: Luke Macken <lmacken@redhat.com>

import re
import sys
import json
import Cookie
import urllib
import urllib2
import getpass
import logging
import cPickle as pickle

from os.path import expanduser, join, isfile
from optparse import OptionParser

log = logging.getLogger(__name__)

__version__ = '$Revision: $'[11:-2]
__description__ = 'Command line tool for interacting with Bodhi'

BODHI_URL = 'http://localhost:8084/updates/'
SESSION_FILE = join(expanduser('~'), '.bodhi_session')

class AuthError(Exception):
    pass

class BodhiClient:
    """
        A command-line client to interact with Bodhi.
    """

    session = None

    def __init__(self, opts):
        self.load_session()

        if opts.new:
            self.new(opts)
        elif opts.masher:
            self.masher(opts)
        elif opts.push:
            self.push(opts)
        elif opts.delete:
            self.delete(opts)
        elif opts.status or opts.bugs or opts.cves or opts.release or opts.type:
            self.list(opts)

    def authenticate(self):
        """
            Return an authenticated session cookie.
        """
        if self.session:
            return self.session

        sys.stdout.write("Username: ")
        sys.stdout.flush()
        username = sys.stdin.readline().strip()
        password = getpass.getpass()

        req = urllib2.Request(BODHI_URL + 'login?tg_format=json')
        req.add_data(urllib.urlencode({
                'user_name' : username,
                'password'  : password,
                'login'     : 'Login'
        }))

        try:
            f = urllib2.urlopen(req)
        except urllib2.HTTPError, e:
            if e.msg == "Forbidden":
                raise AuthError, "Invalid username/password"

        data = json.read(f.read())
        if 'message' in data:
            raise AuthError, 'Unable to login to server: %s' % data['message']

        self.session = Cookie.SimpleCookie()
        try:
            self.session.load(f.headers['set-cookie'])
        except KeyError:
            raise AuthError, "Unable to login to the server.  Server did not" \
                             "send back a cookie."
        self.save_session()

        return self.session

    def save_session(self):
        """
            Store a pickled session cookie.
        """
        s = file(SESSION_FILE, 'w')
        pickle.dump(self.session, s)
        s.close()

    def load_session(self):
        """
            Load a stored session cookie.
        """
        if isfile(SESSION_FILE):
            s = file(SESSION_FILE, 'r')
            try:
                self.session = pickle.load(s)
                log.debug("Loaded session %s" % self.session)
            except EOFError:
                log.error("Unable to load session from %s" % SESSION_FILE)
            s.close()

    def send_request(self, method, auth=False, **kw):
        """
            Send a request to the server.  The given method is called with any
            keyword parameters in **kw.  If auth is True, then the request is
            made with an authenticated session cookie.
        """
        url = BODHI_URL + method + "/?tg_format=json"

        response = None # the JSON that we get back from bodhi
        data = None     # decoded JSON via json.read()

        log.debug("Creating request %s" % url)
        req = urllib2.Request(url)
        req.add_data(urllib.urlencode(kw))

        if auth:
            cookie = self.authenticate()
            req.add_header('Cookie', cookie.output(attrs=[],
                                                   header='').strip())
        try:
            response = urllib2.urlopen(req)
            data = json.read(response.read())
        except urllib2.HTTPError, e:
            log.error(e)
            sys.exit(-1)
        except json.ReadException, e:
            regex = re.compile('<span class="fielderror">(.*)</span>')
            match = regex.search(e.message)
            if match and len(match.groups()):
                log.error(match.groups()[0])
            else:
                log.error("Unexpected ReadException during request:" + e)
            sys.exit(-1)

        return data

    def new(self, opts):
        log.info("Creating new update for %s" % opts.new)
        data = self.send_request('save', builds=opts.new, release=opts.release,
                                 type=opts.type, bugs=opts.bugs, cves=opts.cves,
                                 notes=opts.notes, auth=True)
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
        log.info("%d updates found" % data['num_items'])

    def delete(self, opts):
        data = self.send_request('delete', update=opts.delete, auth=True)
        log.info(data['tg_flash'])

    def masher(self, opts):
        data = self.send_request('admin/masher', auth=True)
        log.info(data['masher_str'])

    def push(self, opts):
        data = self.send_request('admin/push', auth=True)
        log.info("[ %d Pending Requests ]" % len(data['updates']))
        needmove = filter(lambda x: x['request'] == 'move', data['updates'])
        needpush = filter(lambda x: x['request'] == 'push', data['updates'])
        needunpush = filter(lambda x: x['request'] == 'unpush', data['updates'])
        for title, updates in (('Testing', needpush),
                               ('Stable', needmove),
                               ('Obsolete', needunpush)):
            if len(updates):
                log.info("\n" + title)
                for update in updates:
                    log.info(" o %s" % update['title'])

        ## Confirm that we actually want to push these updates
        sys.stdout.write("\nAre you sure you want to push these updates? ")
        sys.stdout.flush()
        yes = sys.stdin.readline().strip()
        if yes in ('y', 'yes'):
            log.info("Pushing!")
            self.send_request('admin/push/mash',
                              updates=[u['title'] for u in data['updates']],
                              auth=True)


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

    # --edit ?

    ## Details
    parser.add_option("-s", "--status", action="store", type="string",
                      dest="status", help="List [testing|pending|requests|"
                                          "stable|security] updates")
    parser.add_option("-b", "--bugs", action="store", type="string",
                      dest="bugs", help="Associate bugs with an update "
                                        "(--bugs=1234,5678)")
    parser.add_option("-c", "--cves", action="store", type="string",
                      dest="cves", help="A list of comma-separated CVE IDs")
    parser.add_option("-r", "--release", action="store", type="string",
                      dest="release", help="Release (default: F7)",
                      default="F7")
    parser.add_option("-N", "--notes", action="store", type="string",
                      dest="notes", help="Update notes")
    parser.add_option("-t", "--type", action="store", type="string",
                      dest="type",
                      help="Update type [bugfix|security|enhancement] "
                           "(default: bugfix)")

    # --package
    # --build (or just take these values from args)

    ## Update actions
    #parser.add_option("-u", "--unpush", action="store", type="string",
    #                  dest="unpush", help="Unpush a given update",
    #                  metavar="UPDATE")
    #parser.add_option("-f", "--feedback", action="store", type="string",
    #                  dest="feedback", metavar="UPDATE",
    #                  help="Give [-1|0|1] feedback about an update")
    #parser.add_option("-C", "--comment", action="store", type="string",
    #                  dest="comment", metavar="UPDATE",
    #                  help="Comment about an update")
    #parser.add_option("-S", "--stable", action="store", type="string",
    #                  dest="stable", metavar="UPDATE",
    #                  help="Mark an update as stable")
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

    BodhiClient(opts)
