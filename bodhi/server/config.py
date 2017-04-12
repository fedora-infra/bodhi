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

import os
import logging

from pyramid.paster import get_appsettings

log = logging.getLogger('bodhi')


def get_configfile():
    configfile = None
    setupdir = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..')
    if configfile:
        if not os.path.exists(configfile):
            log.error("Cannot find config: %s" % configfile)
            return
    else:
        for cfg in (os.path.join(setupdir, 'development.ini'),
                    '/etc/bodhi/production.ini'):
            if os.path.exists(cfg):
                configfile = cfg
                break
        else:
            log.error("Unable to find configuration to load!")
    return configfile


class BodhiConfig(dict):
    loaded = False

    def __getitem__(self, *args, **kw):
        if not self.loaded:
            self.load_config()
        return super(BodhiConfig, self).__getitem__(*args, **kw)

    def get(self, *args, **kw):
        if not self.loaded:
            self.load_config()
        return super(BodhiConfig, self).get(*args, **kw)

    def pop(self, *args, **kw):
        if not self.loaded:
            self.load_config()
        return super(BodhiConfig, self).pop(*args, **kw)

    def copy(self, *args, **kw):
        if not self.loaded:
            self.load_config()
        return super(BodhiConfig, self).copy(*args, **kw)

    def load_config(self):
        configfile = get_configfile()
        self.update(get_appsettings(configfile))
        self.loaded = True


config = BodhiConfig()
