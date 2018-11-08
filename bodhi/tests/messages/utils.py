# Copyright (C) 2018-2019 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""Utilities to do unit testing of message schemas."""

import typing

if typing.TYPE_CHECKING:  # pragma: no cover
    from bodhi.messages.schemas.base import BodhiMessage  # noqa: 401


def check_message(msg: 'BodhiMessage', expected: typing.Mapping[str, typing.Any]):
    """
    Assert that the given message matches the information described in the expected mapping.

    Args:
        msg: The message you wish to validate.
        expected: A dictionary describing the attributes that msg should have. Each key must match
            the name of an attribute on msg, and will be used to compare the attribute's value to
            the expected dictionary's value. A special key, __str__, may be used in expected to
            index a string for how the message should be rendered by str().
    """
    # Let's make sure the message matches the expected schema.
    msg.validate()
    for prop, expected_value in expected.items():
        if prop == "__str__":
            assert str(msg) == expected_value
        else:
            assert getattr(msg, prop) == expected_value, (
                f"key {prop} does not match: msg has {getattr(msg, prop)}, "
                f"expected is {expected_value}")
