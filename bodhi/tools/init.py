#!/usr/bin/env python
#
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

""" Bodhi Initialization """

from os.path import isfile
from turbogears import config, update_config
from turbogears.database import PackageHub

hub = PackageHub("bodhi")
__connection__ = hub

releases = (
    {
        'name'      : 'F7',
        'long_name' : 'Fedora 7',
        'dist_tag'  : 'dist-fc7',
        'id_prefix' : 'FEDORA'
    },
    {
        'name'      : 'F8',
        'long_name' : 'Fedora 8',
        'dist_tag'  : 'dist-f8',
        'id_prefix' : 'FEDORA'
    },
)

def import_releases():
    """ Import the releases """
    from bodhi.model import Release
    print "\nInitializing Release table..."

    for release in releases:
        rel = Release(name=release['name'], long_name=release['long_name'],
                      id_prefix=release['id_prefix'],
                      dist_tag=release['dist_tag'])
        print rel

def import_rebootpkgs():
    """
    Add packages that should suggest a reboot.  Other than these packages, we
    add a package to the database when its first update is added to the system
    """
    from bodhi.model import Package
    for pkg in config.get('reboot_pkgs').split():
        Package(name=pkg, suggest_reboot=True)

def clean_tables():
    from bodhi.model import Release, Package
    print "Cleaning out tables"
    Release.dropTable(ifExists=True, cascade=True)
    Package.dropTable(ifExists=True, cascade=True)
    hub.commit()
    Release.createTable(ifNotExists=True)
    Package.createTable(ifNotExists=True)

def load_config():
    """ Load the appropriate configuration so we can get at the values """
    configfile = 'prod.cfg'
    if not isfile(configfile):
        configfile = 'bodhi.cfg'
    update_config(configfile=configfile, modulename='bodhi.config')

##
## Initialize the package/release/multilib tables
##
if __name__ == '__main__':
    print "Initializing Bodhi\n"
    load_config()
    hub.begin()
    clean_tables()
    import_releases()
    import_rebootpkgs()
    hub.commit()
