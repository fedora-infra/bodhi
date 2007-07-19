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
import cPickle as pickle

from os.path import expanduser, join, isfile
from optparse import OptionParser

__version__ = '$Revision: $'[11:-2]
__description__ = 'Command line tool for interacting with Bodhi'

BODHI_URL = 'http://localhost:8084/updates/'

class AuthError(Exception):
    pass

class BodhiClient:
    """
    A command-line client to interact with a Bodhi instance.

    TODO:
        - only authenticate() when necessary
            - otherwise, get session from another get_session() method?
    """

    session = None

    def __init__(self, opts):
        self.session_file = join(expanduser('~'), '.bodhi-session')
        self.load_session()

        if opts.new:
            self.new(opts)

    def authenticate(self):
        if self.session:
            print "Using existing session"
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

        f = urllib2.urlopen(req)
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
        s = file(self.session_file, 'w')
        print "Writing out session: %s" % self.session
        pickle.dump(self.session, s)
        s.close()

    def load_session(self):
        if isfile(self.session_file):
            s = file(self.session_file, 'r')
            try:
                self.session = pickle.load(s)
                print "Loaded session", self.session
            except EOFError:
                print "Unable to load session from %s" % self.session_file
            s.close()

    def send_request(self, method, cookie=False, **kw):
        url = BODHI_URL + method + "/?tg_format=json"
        for key, value in kw.items():
            url += "&%s=%s" % (key, value)

        print "Creating request %s" % url

        req = urllib2.Request(url)
        #req = urllib2.Request("http://localhost:8084/updates/save/?tg_format="
        #                      "json&builds=python-virtinst-0.200.0-1.fc7&"
        #                      "release=Fedora%207&type=bugfix&bugs=1&cves="
        #                      "CVE-2007-0001&notes=foobar")

        if cookie:
            req.add_header('Cookie', cookie.output(attrs=[], header='').strip())
        f = urllib2.urlopen(req)

        try:
            return json.read(f.read())
        except json.ReadException, e:
            regex = re.compile('<span class="fielderror">(.*)</span>')
            match = regex.search(e.message)
            if len(match.groups()):
                print "Error:", match.groups()[0]
            else:
                print "Unexpected ReadException during request:", e
            sys.exit(-1)

    def new(self, opts):
        print "Creating new update"
        self.authenticate()
        data = self.send_request('save', builds=opts.new, release=opts.release,
                                 type=opts.type, bugs=opts.bugs, cves=opts.cves,
                                 notes=opts.notes)
        print data['tg_flash']
        if data.has_key('update'):
            print data['update']

    def stable(self):
        raise NotImplementedError

    def comment(self):
        raise NotImplementedError

    def list(self):
        """ List updates by status/request/bug/cve """
        raise NotImplementedError


if __name__ == '__main__':
    usage = "usage: %prog [options]"
    parser = OptionParser(usage, description=__description__)

    ## Actions
    parser.add_option("-n", "--new", action="store", type="string", dest="new",
                      help="Add a new update to the system (--new=foo-1.2-3,"
                           "bar-4.5-6)")
    parser.add_option("-l", "--list", action="store", type="string",
                      metavar="STATUS", dest="list",
                      help="List [testing|pending|requests|stable|security] "
                           "updates")

    ## Details
    parser.add_option("-b", "--bugs", action="store", type="string",
                      dest="bugs", default="",
                      help="Associate bugs with an update (--bugs=1234,5678)")
    parser.add_option("-c", "--cves", action="store", type="string",
                      dest="cves", default="",
                      help="A list of comma-separated CVE IDs")
    parser.add_option("-r", "--release", action="store", type="string",
                      dest="release", default="F7",
                      help="Release (default: F7)")
    parser.add_option("-N", "--notes", action="store", type="string",
                      dest="notes", default="", help="Update notes")
    parser.add_option("-t", "--type", action="store", type="string",
                      dest="type", default="bugfix",
                      help="Update type [bugfix|security|enhancement] "
                           "(default: bugfix)")

    ## Update actions
    parser.add_option("-u", "--unpush", action="store", type="string",
                      dest="unpush", help="Unpush a given update",
                      metavar="UPDATE")
    (options, args) = parser.parse_args()

    BodhiClient(options)
