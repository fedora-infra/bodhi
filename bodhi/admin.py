# $Id: admin.py,v 1.3 2007/01/08 06:07:07 lmacken Exp $
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

import logging
import cherrypy
import simplejson
import cPickle as pickle

from os.path import join, exists
from Cookie import SimpleCookie
from turbogears import expose, identity, redirect, flash, config
from turbogears.identity import SecureResource
from turbogears.controllers import Controller

from fedora.tg.util import request_format
from fedora.client.proxyclient import ProxyClient

from bodhi.util import flash_log
from bodhi.masher import Masher
from bodhi.model import Release, PackageUpdate


log = logging.getLogger(__name__)

class AdminController(Controller, SecureResource):
    """
    The bodhi administration controller
    """
    require = identity.in_group("releng")

    @expose(template='bodhi.templates.admin')
    def index(self):
        return dict()

    @expose(template='bodhi.templates.masher', allow_json=True)
    def masher(self):
        """ Display the current status of the Masher """
        if config.get('masher'):
            data = self._masher_request('/admin/masher')
            return dict(masher_str=data['masher_str'], tags=data['tags'])
        else:
            tags = []
            for release in Release.select():
                tags.append('%s-updates' % release.dist_tag)
                tags.append('%s-updates-testing' % release.dist_tag)
            return dict(masher_str=str(Masher()), tags=tags)

    @expose(template='bodhi.templates.text')
    def lastlog(self):
        """ Return the last mash log """
        (logfile, data) = Masher().lastlog()
        return dict(title=logfile, text=data)

    @expose(allow_json=True)
    def mash_tag(self, tag, **kw):
        """ Kick off a mash for a given tag """
        log.debug("mash_tags(%s, %s)" % (repr(tag), repr(kw)))
        if config.get('masher'):
            data = self._masher_request('/admin/mash_tag', tag=tag)
            flash_log("Mash request %s" % data.get('success') and
                      "succeeded" or "failed")
        else:
            Masher().mash_tags([tag])
            flash_log("Mashing tag: %s" % tag)
        raise redirect('/admin/masher')

    @expose(template='bodhi.templates.push', allow_json=True)
    def push(self):
        """ List updates tagged with a push/unpush/move request """
        updates = []
        resume = False
        mash = self._current_mash()
        if mash['mashing']:
            flash_log('The masher is currently pushing updates')
        else:
            updates = map(PackageUpdate.byTitle, mash.get('updates', []))
            if updates:
                flash_log('There is an updates push ready to be resumed')
                resume = True
            else:
                # Get a list of all updates with a request that aren't
                # unapproved security updates, or for a locked release
                requests = filter(lambda update: not update.release.locked,
                                  PackageUpdate.select(
                                      PackageUpdate.q.request != None))
                for update in requests:
                    if update.type == 'security' and not update.approved:
                        continue
                    updates.append(update)
        return dict(updates=updates, resume=resume)

    @expose(allow_json=True)
    def mash(self, updates, resume=False, **kw):
        """ Mash a list of PackageUpdate objects.

        If this instance is deployed with a remote masher, then it simply
        proxies the request.  If we are the masher, then send these updates to
        our Mash instance.  This will then start a thread that takes care of
        handling all of the update requests, composing fresh repositories,
        generating and sending update notices, closing bugs, etc.
        """
        if request_format() == 'json':
            updates = simplejson.loads(updates.replace("u'", "\"").replace("'", "\""))
        if not isinstance(updates, list):
            updates = [updates]

        # If we're not The Masher, then proxy this request to it
        if config.get('masher'):
            data = self._masher_request('/admin/mash', updates=updates)
            flash_log('Push request %s' % data.get('success') and 'succeeded'
                                                               or 'failed')
            raise redirect('/admin/masher')

        Masher().queue([PackageUpdate.byTitle(title) for title in updates],
                       resume=resume)
        if request_format() == 'json':
            return dict(success=True)
        flash("Updates queued for mashing")
        raise redirect('/admin/masher')

    @expose(allow_json=True)
    def current_mash(self):
        """ Get the update list for the current mash """
        mash_data = None
        if config.get('masher'):
            data = self._masher_request('/admin/current_mash')
            mash_data = data.get('mash')
            if mash_data['mashing']:
                flash_log('The masher is currently pushing updates')
            else:
                flash_log('There is an updates push ready to be resumed')
        else:
            mashed_dir = config.get('mashed_dir')
            mash_lock = join(mashed_dir, 'MASHING')
            if exists(mash_lock):
                mash_lock = file(mash_lock)
                mash_data = pickle.load(mash_lock)
                mash_lock.close()
                mash_data = {'mashing': Masher().mashing, 'updates': mash_data}
        return dict(mash=mash_data)

    def _masher_request(self, method, kwargs=None):
        """
        Call a remote method on the masher with any other arguments.
        Returns whatever the remote method returned to us.
        """
        log.debug('Calling remote method "%s" with %s' % (method, kwargs))
        try:
            client = ProxyClient(config.get('masher'), debug=True)
            cookie = SimpleCookie(cherrypy.request.headers.get('Cookie'))
            session, data = client.send_request(method,
                                                auth_params={'cookie': cookie},
                                                **kwargs)
            log.debug("Remote method returned %s" % repr(data))
            if data.get('tg_flash'):
                flash_log(data['tg_flash'])
            return data
        except Exception, e:
            flash_log("Error: %s" % str(e))
            import traceback; traceback.print_exc()
