# Copyright © 2020 Red Hat, Inc. and others.
#
# This file is part of Bodhi.
#
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
from graphene.test import Client

from bodhi.tests.server import base
from bodhi.server.services.graphql import schema
from bodhi.server.models import PackageManager, Release


class TestGraphQLService(base.BasePyTestCase):
    """This class contains tests for a /graphql endpoint."""
    def test_get(self):
        """Ensure that a GraphQL response is returned"""
        res = self.app.get('/graphql?query={%0A%20 allReleases{%0A%20%20%20 name%0A%20 }%0A}')
        assert res.body == b'{"data":{"allReleases":[{"name":"F17"}]}}'

    def test_allReleases(self):
        """Testing allReleases."""
        client = Client(schema)
        release = Release(
            name='F22', long_name='Fedora 22',
            id_prefix='FEDORA', version='22',
            dist_tag='f22', stable_tag='f22-updates',
            testing_tag='f22-updates-testing',
            candidate_tag='f22-updates-candidate',
            pending_signing_tag='f22-updates-testing-signing',
            pending_testing_tag='f22-updates-testing-pending',
            pending_stable_tag='f22-updates-pending',
            override_tag='f22-override',
            branch='f22',
            package_manager=PackageManager.dnf,
            testing_repository='updates-testing')

        self.db.add(release)
        self.db.commit()

        executed = client.execute("""{  allReleases{  name  }}""")
        assert executed == {
            "data": {
                "allReleases": [{
                    "name": "F17"
                }, {
                    "name": "F22"
                }]
            }
        }

    def test_enumfields(self):
        """Testing enum fields on releases."""
        client = Client(schema)
        release = Release(
            name='F22', long_name='Fedora 22',
            id_prefix='FEDORA', version='22',
            dist_tag='f22', stable_tag='f22-updates',
            testing_tag='f22-updates-testing',
            candidate_tag='f22-updates-candidate',
            pending_signing_tag='f22-updates-testing-signing',
            pending_testing_tag='f22-updates-testing-pending',
            pending_stable_tag='f22-updates-pending',
            override_tag='f22-override',
            branch='f22',
            package_manager=PackageManager.dnf,
            testing_repository='updates-testing')

        self.db.add(release)
        self.db.commit()

        executed = client.execute("""{  allReleases{  state    packageManager  }}""")
        assert executed == {
            'data': {
                'allReleases': [{
                    'packageManager': 'unspecified',
                    'state': 'current'
                }, {
                    'packageManager': 'dnf',
                    'state': 'disabled'
                }]
            }
        }
