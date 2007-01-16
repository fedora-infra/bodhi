# $Id: json.py,v 1.3 2006/12/31 09:10:14 lmacken Exp $
# This module provides helper functions for the JSON part of your
# view, if you are providing a JSON-based API for your app.

# Here's what most rules would look like:
# @jsonify.when("isinstance(obj, YourClass)")
# def jsonify_yourclass(obj):
#     return [obj.val1, obj.val2]
# The goal is to break your objects down into simple values:
# lists, dicts, numbers and strings
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

from turbojson.jsonify import jsonify
from turbojson.jsonify import jsonify_sqlobject
from bodhi.model import User, Group, Permission

@jsonify.when('isinstance(obj, Group)')
def jsonify_group(obj):
    result = jsonify_sqlobject( obj )
    result["users"] = [u.user_name for u in obj.users]
    result["permissions"] = [p.permission_name for p in obj.permissions]
    return result

@jsonify.when('isinstance(obj, User)')
def jsonify_user(obj):
    result = jsonify_sqlobject( obj )
    del result['password']
    result["groups"] = [g.group_name for g in obj.groups]
    result["permissions"] = [p.permission_name for p in obj.permissions]
    return result

@jsonify.when('isinstance(obj, Permission)')
def jsonify_permission(obj):
    result = jsonify_sqlobject( obj )
    result["groups"] = [g.group_name for g in obj.groups]
    return result
