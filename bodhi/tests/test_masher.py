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

from bodhi.models import Update
from bodhi.masher import Masher
from bodhi.tests.functional.base import BaseWSGICase


class FakeHub(object):
    config = {
        'topic_prefix': 'org.fedoraproject',
        'environment': 'dev',
        'masher_topic': 'bodhi.start',
        'masher': True,
    }

    def subscribe(self, *args, **kw):
        pass


def makemsg(body=None):
    if not body:
        body = {'updates': 'bodhi-2.0-1.fc17'}
    return {
        'topic': u'org.fedoraproject.dev.bodhi.masher.start',
        'body': {
            u'i': 1,
            u'msg': body,
            u'msg_id': u'2014-9568c910-91de-4870-90f5-709cc577d56d',
            u'timestamp': 1401728063,
            u'topic': u'org.fedoraproject.dev.bodhi.masher.start',
            u'username': u'lmacken',
        },
    }


class TestMasher(BaseWSGICase):

    def setUp(self):
        super(TestMasher, self).setUp()
        self.masher = Masher(FakeHub())

    def test_basic_consume(self):
        self.assertEquals(self.db.query(Update).count(), 1)
        self.masher.consume(makemsg())
