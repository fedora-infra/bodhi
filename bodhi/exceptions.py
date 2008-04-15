# $Id: $
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

class BodhiException(Exception):
    pass

class RPMNotFound(BodhiException):
    pass

class RepositoryLocked(BodhiException):
    pass

class RepositoryNotFound(BodhiException):
    pass

class InvalidRequest(BodhiException):
    pass

try:
    from sqlobject.dberrors import DuplicateEntryError
except ImportError:
    # Handle pre-DuplicateEntryError versions of SQLObject
    class DuplicateEntryError(Exception): pass

from psycopg2 import IntegrityError as PostgresIntegrityError
try:
    from pysqlite2.dbapi2 import IntegrityError as SQLiteIntegrityError
except:
    from sqlite import IntegrityError as SQLiteIntegrityError
