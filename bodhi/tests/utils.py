# -*- coding: utf-8 -*-
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

import re


def prepare_text_for_comparison(text):
    """Transfer wrapped text output to one line."""
    text = text.replace('\n', '')  # Remove newlines
    text = re.sub(r' +:', '', text)  # Remove start of wrapped lines
    text = "".join(text.split())  # Remove whitespaces
    return text


def compare_output(output, expected):
    """Compare content of wrapped text outputs and show diff if enabled."""
    output = prepare_text_for_comparison(output)
    expected = prepare_text_for_comparison(expected)
    return output == expected
