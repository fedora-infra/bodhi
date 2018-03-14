#!/usr/bin/bash -ex
# Copyright (c) 2017 Red Hat, Inc.
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

# This script is intended to be run inside the test containers. It runs style tests, builds the
# docs, runs the unit tests, moves results into /results to be collected, and ensures that new code
# has 100% test coverage.

fail() {
    echo "JENKIES FAIL!"
    exit 1
}

gather_results() {
    mv docs/_build/html /results/docs
    cp *.xml /results
}

sed -i '/pyramid_debugtoolbar/d' setup.py
sed -i '/pyramid_debugtoolbar/d' devel/development.ini.example

cp devel/development.ini.example development.ini

/usr/bin/python setup.py develop || fail

/usr/bin/tox || fail
/usr/bin/py.test-2 $@ || (gather_results; fail)
/usr/bin/py.test-3 $@ || (gather_results; fail)

gather_results

diff-cover coverage.xml --compare-branch=origin/develop --fail-under=100 || fail
