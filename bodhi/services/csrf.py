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

from cornice import Service


csrf = Service(name='csrf', path='/csrf', description='CSRF Token')


@csrf.get(accept="text/html", renderer="string")
def get_csrf_token_html(request):
    return request.session.get_csrf_token()


@csrf.get(accept=("application/json", "text/json"), renderer="json")
def get_csrf_token_json(request):
    return dict(csrf_token=request.session.get_csrf_token())
