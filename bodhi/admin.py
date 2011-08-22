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
from sqlobject import SQLObjectNotFound
from formencode import validators
from turbogears import expose, identity, redirect, flash, config, validate
from turbogears.identity import SecureResource
from turbogears.controllers import Controller

try:
    from fedora.tg.tg1utils import request_format
except ImportError:
    from fedora.tg.util import request_format

from fedora.client.proxyclient import ProxyClient

from bodhi.util import flash_log
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
            if not data:
                data = {'masher_str': 'Unable to contact the masher','tags': []}
            return dict(masher_str=data['masher_str'], tags=data['tags'])
        else:
            from bodhi.masher import masher
            tags = []
            for release in Release.select():
                tags.append(release.stable_tag)
                tags.append(release.testing_tag)
            return dict(masher_str=str(masher), tags=tags)

    @expose(template='bodhi.templates.text')
    def lastlog(self):
        """ Return the last mash log """
        from bodhi.masher import masher
        (logfile, data) = masher.lastlog()
        return dict(title=logfile, text=data)

    @expose(allow_json=True)
    def mash_tag(self, tag, **kw):
        """ Kick off a mash for a given tag """
        log.debug("mash_tag(%s)" % locals())
        if config.get('masher'):
            data = self._masher_request('/admin/mash_tag', tag=tag)
            if not data:
                flash_log("Mash request failed.  There may be an "
                          "existing mash that needs to be resumed first.")
            else:
                flash_log("Mash request %s" %
                          data.get('success', 'failed'))
        else:
            from bodhi.masher import masher
            masher.mash_tags([tag])
            flash_log("Mashing tag: %s" % tag)
        raise redirect('/admin/masher')

    @expose(template='bodhi.templates.push', allow_json=True)
    def push(self):
        """ List updates tagged with a push/unpush/move request """
        updates = []
        resume = False
        mash = self._current_mash()
        if not mash:
            flash_log("A masher exception has occured.")
            return dict(updates=[], resume=False)
        if mash['mashing']:
            flash_log('The masher is currently pushing updates')
        else:
            for update in mash.get('updates', []):
                try:
                    updates.append(PackageUpdate.byTitle(update))
                except SQLObjectNotFound:
                    log.warning("Cannot find update %s in push queue" % update)
            if updates:
                flash_log('There is an updates push ready to be resumed')
                resume = True
            else:
                # Get a list of all updates with a request that aren't
                # unapproved security updates, or for a locked release
                requests = PackageUpdate.select(PackageUpdate.q.request != None)

                # Come F13+, bodhi will not have locked releases.  It will 
                # implement the 'No Frozen Rawhide' proposal, and treat 'locked'
                # releases as pending.
                #requests = filter(lambda update: not update.release.locked,
                #                  PackageUpdate.select(
                #                      PackageUpdate.q.request != None))
                for update in requests:
                    # Disable security approval requirement
                    #if update.type == 'security' and not update.approved:
                    #    continue
                    updates.append(update)
        return dict(updates=updates, resume=resume)

    @expose(allow_json=True)
    @validate(validators={'resume' : validators.StringBool()})
    def mash(self, updates=None, resume=False, **kw):
        """ Mash a list of PackageUpdate objects.

        If this instance is deployed with a remote masher, then it simply
        proxies the request.  If we are the masher, then send these updates to
        our Mash instance.  This will then start a thread that takes care of
        handling all of the update requests, composing fresh repositories,
        generating and sending update notices, closing bugs, etc.
        """
        if not updates:
            updates = []
        if not isinstance(updates, list):
            if isinstance(updates, basestring):
                log.debug("Doing simplejson hack")
                try:
                    updates = simplejson.loads(updates.replace("u'", "\"").replace("'", "\""))
                except:
                    log.debug("Didn't work, assuming it's a single update...")
                    updates = [updates]
            else:
                updates = [updates]

        # If we're not The Masher, then proxy this request to it
        if config.get('masher'):
            data = self._masher_request('/admin/mash', updates=updates, resume=resume) or {}
            flash_log('Push request %s' % (data.get('success') and 'succeeded'
                                                                or 'failed'))
            raise redirect('/admin/masher')

        from bodhi.masher import masher
        masher.queue([PackageUpdate.byTitle(title) for title in updates],
                     resume=resume)
        if request_format() == 'json':
            return dict(success=True)
        flash("Updates queued for mashing")
        raise redirect('/admin/masher')

    def _current_mash(self):
        """ Return details about the mash in process """
        if config.get('masher', None):
            return self._masher_request('/admin/current_mash')

        from bodhi.masher import masher
        mash_data = {'mashing': False, 'updates': []}
        mashed_dir = config.get('mashed_dir')
        masher_lock_id = config.get('masher_lock_id', 'FEDORA')
        mash_lock = join(mashed_dir, 'MASHING-%s' % masher_lock_id)
        if exists(mash_lock):
            mash_lock = file(mash_lock)
            mash_state = pickle.load(mash_lock)
            mash_lock.close()
            mash_data['mashing'] = masher.mashing
            log.debug('mash_state = %s' % repr(mash_state))
            mash_data['updates'] = mash_state['updates']
        return mash_data

    @expose(allow_json=True)
    def current_mash(self):
        """ Return details about the mash in process """
        return self._current_mash()

    def _get_mash_status(self):
        """ Return details about the mash in process """

    def _masher_request(self, method, **kwargs):
        """
        Call a remote method on the masher with any other arguments.
        Returns whatever the remote method returned to us.
        """
        log.debug('Calling remote method "%s" with %s' % (method, kwargs))
        try:
            client = ProxyClient(config.get('masher'))
            cookie = SimpleCookie(cherrypy.request.headers.get('Cookie'))
            session, data = client.send_request(method,
                                                auth_params={'session_id': cookie.get('tg-visit').value},
                                                req_params=kwargs)
            log.debug("Remote method returned %s" % repr(data))
            if data.get('tg_flash'):
                flash_log(data['tg_flash'])
            return data
        except Exception, e:
            flash_log("Error: %s" % str(e))
            log.exception(e)
