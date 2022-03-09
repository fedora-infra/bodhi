# Copyright © 2018 Red Hat, Inc.
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
"""This module contains useful functions that helps with testing."""

from io import BytesIO
import difflib
import re

from requests import Response


def prepare_text_for_comparison(text):
    """Transfer wrapped text output to one line."""
    text = text.replace('\n', '')  # Remove newlines
    text = re.sub(r' +:', '', text)  # Remove start of wrapped lines
    text = "".join(text.split())  # Remove whitespaces
    return text


def compare_output(output, expected, debug_output=False):
    """Compare content of wrapped text outputs and show diff if enabled."""
    prepared_output = prepare_text_for_comparison(output)
    prepared_expected = prepare_text_for_comparison(expected)
    if prepared_output == prepared_expected:
        return True
    else:
        if debug_output:
            differ = difflib.Differ()
            diff = differ.compare(output.splitlines(True),
                                  expected.splitlines(True))
            print(''.join(list(diff)))
        return False


def build_response(status_code, url, content):
    """Build a response with the provided parameters.

    Args:
        status_code (int): The HTTP status code.
        url (str): The URL that was requested.
        content (str): The response content.

    Returns:
        requests.Response: A Response object compatible with ``requests``.
    """
    response = Response()
    response.status_code = status_code
    response.url = url
    response.encoding = "utf-8"
    response.raw = BytesIO(content.encode("utf-8"))
    return response
