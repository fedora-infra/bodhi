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
import datetime

from graphene.test import Client

from bodhi.tests.server import base
from bodhi.server.services.graphql import schema
from bodhi.server import models


class TestGraphQLService(base.BasePyTestCase):
    """This class contains tests for a /graphql endpoint."""
    def test_get(self):
        """Ensure that a GraphQL response is returned"""
        res = self.app.get('/graphql?query={%0A%20 allReleases{%0A%20%20%20 name%0A%20 }%0A}')
        assert res.body == b'{"data":{"allReleases":[{"name":"F17"}]}}'

    def test_allReleases(self):
        """Testing allReleases."""
        base.BaseTestCaseMixin.create_release(self, version='22')
        client = Client(schema)
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
        base.BaseTestCaseMixin.create_release(self, version='22')
        client = Client(schema)
        self.db.commit()

        executed = client.execute("""{  allReleases{  state    packageManager  }}""")
        assert executed == {
            'data': {
                'allReleases': [{
                    'packageManager': 'unspecified',
                    'state': 'current'
                }, {
                    'packageManager': 'unspecified',
                    'state': 'current'
                }]
            }
        }

    def test_getReleases(self):
        """Testing getReleases query."""
        base.BaseTestCaseMixin.create_release(self, version='22')
        client = Client(schema)
        self.db.commit()

        executed = client.execute("""{  getReleases(idPrefix: "FEDORA"){  name  }}""")
        assert executed == {
            "data": {
                "getReleases": [{
                    "name": "F17"
                }, {
                    "name": "F22"
                }]
            }
        }

        executed = client.execute("""{  getReleases(name: "F17"){  id  }}""")
        assert executed == {
            "data": {
                "getReleases": [{
                    "id": "UmVsZWFzZTox"
                }]
            }
        }

        executed = client.execute("""{  getReleases(composedByBodhi: true){  name  }}""")
        assert executed == {
            "data": {
                "getReleases": [{
                    "name": "F17"
                }, {
                    "name": "F22"
                }]
            }
        }

        executed = client.execute(
            """{  getReleases(state: "current", composedByBodhi: true){  name  }}""")
        assert executed == {
            "data": {
                "getReleases": [{
                    "name": "F17"
                }, {
                    "name": "F22"
                }]
            }
        }

    def test_getUpdates(self):
        """Testing getUpdates query."""
        release = base.BaseTestCaseMixin.create_release(self, version='22')
        self.create_update(build_nvrs=['TurboGears-2.1-1.el5'],
                           release_name=release.name)
        up2 = self.create_update(build_nvrs=['freetype-2.10.2-1.fc32'],
                                 release_name=release.name)
        up2.alias = "FEDORA-2020-3223f9ec8b"
        up2.stable_days = 1
        up2.date_approved = datetime.datetime(2019, 10, 13, 16, 16, 22, 438484)
        self.db.commit()
        client = Client(schema)

        executed = client.execute("""{  getUpdates(stableDays: 1,
                                  dateApproved: "2019-10-13 16:16:22.438484")
                                  {  alias  request  unstableKarma  }}""")
        assert executed == {
            "data": {
                "getUpdates": [{
                    "alias": "FEDORA-2020-3223f9ec8b",
                    "request": "testing",
                    "unstableKarma": -3
                }]
            }
        }

        executed = client.execute("""{  getUpdates(stableKarma: 3, status: "pending",
                                  critpath: false, pushed: false, request:"testing"){  stableDays
                                  userId  }}""")
        assert executed == {
            'data': {
                'getUpdates': [{
                    'stableDays': 0,
                    'userId': 1
                }, {
                    'stableDays': 0,
                    'userId': 1
                }, {
                    'stableDays': 1,
                    'userId': 1
                }]
            }
        }

        executed = client.execute("""{  getUpdates(stableDays: 1,
                                  unstableKarma: -3, alias: "FEDORA-2020-3223f9ec8b")
                                  {  dateApproved  request  }}""")
        assert executed == {
            'data': {
                'getUpdates': [{
                    'dateApproved': "2019-10-13 16:16:22.438484",
                    'request': 'testing'
                }]
            }
        }

        executed = client.execute("""{  getUpdates(critpath: false, stableDays: 1,
                                  userId: 1){  request    unstableKarma  }}""")
        assert executed == {
            'data': {
                'getUpdates': [{
                    'request': 'testing',
                    'unstableKarma': -3,
                }]
            }
        }

        executed = client.execute("""{  getUpdates(releaseName: "F22"){  request  }}""")
        assert executed == {
            'data': {
                'getUpdates': [{
                    'request': 'testing',
                }, {
                    'request': 'testing',
                }]
            }
        }

    def test_getBuildrootOverrides(self):
        """Testing getBuildOverrides query."""
        release = models.Release.get('F17')

        package = models.RpmPackage(name='just-testing')
        self.db.add(package)
        build = models.RpmBuild(nvr='just-testing-1.0-2.fc17', package=package, release=release)
        self.db.add(build)
        another_user = models.User(name='aUser')
        self.db.add(another_user)

        expiration_date = datetime.datetime(2020, 10, 13, 16, 16, 22, 438484)
        submission_date = datetime.datetime(2020, 10, 12, 16, 16, 22, 438484)

        override = models.BuildrootOverride(build=build, submitter=another_user,
                                            notes='Crazy! 😱',
                                            expiration_date=expiration_date,
                                            submission_date=submission_date)
        self.db.add(override)
        self.db.flush()
        client = Client(schema)
        self.db.commit()

        executed = client.execute("""{  getBuildrootOverrides(buildNvr: "just-testing-1.0-2.fc17")
                                  {  submissionDate  expirationDate  }}""")
        assert executed == {
            'data': {
                'getBuildrootOverrides': [{
                    'expirationDate': "2020-10-13T16:16:22.438484",
                    'submissionDate': "2020-10-12T16:16:22.438484",
                }]
            }
        }

        executed = client.execute("""{  getBuildrootOverrides(submissionDate: "2020-10-12T16:16:22.438484",
                                  expirationDate: "2020-10-13T16:16:22.438484")
                                  {  notes  }}""")
        assert executed == {
            'data': {
                'getBuildrootOverrides': [{
                    'notes': "Crazy! 😱"
                }]
            }
        }

        executed = client.execute("""{  getBuildrootOverrides(submitterUsername: "aUser",
                                  expirationDate: "2020-10-13T16:16:22.438484")
                                  {  notes  }}""")
        assert executed == {
            'data': {
                'getBuildrootOverrides': [{
                    'notes': "Crazy! 😱"
                }]
            }
        }
