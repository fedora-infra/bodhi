# $Id: buildsys.py,v 1.5 2007/01/06 08:03:21 lmacken Exp $
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

import os
import util

from turbogears import config
from exceptions import Exception

class SRPMNotFound(Exception):
    pass

class Buildsys:
    """ Parent buildsystem class """

    def get_srpm_path(self, update):
        """ Get the SRPM path for a given package update """
        pass

    def get_source_path(self, update):
        """ Get the source path for a given package update """
        pass

class Brew(Buildsys):
    pass

class Plague(Buildsys):
    """
    We want to talk to buildsys.fedoraproject.org and grab plague-results.
    Some ideas have been to rsync the tree locally, or using FUSE sshfs.
    """
    pass

class LocalTest(Buildsys):
    """ Local test source repo, where a buildsystem is not present.  Here we
        are just using the 'build_dir' directory inside this project for
        testing.
    """

    def get_source_path(self, update):
        """
        Return the path to the built package.  For the LocalTest repository
        we'll return the following:
                build_dir/package/version/release
        """
        build_dir = config.get('build_dir')
        assert build_dir
        return os.path.join(build_dir, *util.get_nvr(update.nvr))

    def get_srpm_path(self, update):
        srpm = os.path.join(self.get_source_path(update), "src",
                            "%s.src.rpm" % update.nvr)
        if not os.path.isfile(srpm):
            raise SRPMNotFound
        return srpm

## We're dealing with local testing first
buildsys = LocalTest()
