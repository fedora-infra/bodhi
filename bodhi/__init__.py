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
"""Fedora's update manager."""

__version__ = "5.7.0"

# This is a regular expression used to match username mentions in comments.
MENTION_RE = r'(?<!\S)(@\w+)'

# Setuptools common parameters
_setuptools_config = {
    'version': __version__,
    'classifiers': [
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Topic :: System :: Software Distribution',
    ],
    'license': 'GPLv2+',
    'maintainer': 'Fedora Infrastructure Team',
    'maintainer_email': 'infrastructure@lists.fedoraproject.org',
    'platforms': ['Fedora', 'GNU/Linux'],
    'url': 'https://github.com/fedora-infra/bodhi',
    'zip_safe': False,
}
