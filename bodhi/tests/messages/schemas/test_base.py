# Copyright © 2019 Red Hat, Inc.
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
"""This test module contains tests for bodhi.messages.schemas.base."""

import json

import pytest

from bodhi.messages.schemas import base


class TestFedMsgEncoder:
    """Tests for the custom JSON encode ``FedMsgEncoder``."""

    def test_default(self):
        """Assert normal types are encoded the same way as the default encoder."""
        assert json.dumps('a string') == json.dumps('a string', cls=base.FedMsgEncoder)

    def test_default_obj_with_json(self):
        """Assert classes with a ``__json__`` function encode as the return of ``__json__``."""

        class JsonClass(object):
            def __json__(self):
                return {'my': 'json'}

        assert {'my': 'json'} == base.FedMsgEncoder().default(JsonClass())

    def test_default_other(self):
        """Fallback to the superclasses' default."""
        with pytest.raises(TypeError):
            base.FedMsgEncoder().default(object())
