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

import unittest
from bodhi.masher import Masher


class FakeHub(object):
    config = {
        'topic_prefix': 'org.fedoraproject',
        'environment': 'dev',
        'masher_topic': 'bodhi.start',
        'masher': True,
    }
    def noop(self, *args, **kw):
        pass

    subscribe = noop


fake_msg = {
    'body': {u'i': 1, u'msg': {u'log': u'foo'}, u'msg_id':
    u'2014-9568c910-91de-4870-90f5-709cc577d56d', u'timestamp': 1401728063,
    u'topic': u'org.fedoraproject.dev.bodhi.masher.start', u'username':
    u'lmacken'}, 'topic': u'org.fedoraproject.dev.bodhi.masher.start'
}


class TestMasher(unittest.TestCase):

    def setUp(self):
        self.masher = Masher(FakeHub())

    def test_basic_consume(self):
        self.masher.consume(fake_msg)
