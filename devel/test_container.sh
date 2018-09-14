#!/usr/bin/bash -ex
# Copyright (c) 2017-2018 Red Hat, Inc.
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

# The TEST_TYPE variable can be set to get it to focus on just one type of test (it defaults to
# running all tests.) It can be set to flake8, pydocstyle, docs, or unit.

fail() {
    echo "JENKIES FAIL!"
    exit 1
}

gather_results() {
    if [ -z "${TEST_TYPE}" ] || [ "${TEST_TYPE}" == "docs" ]; then
        mv docs/_build/html /results/docs
    fi
    if [ -z "${TEST_TYPE}" ] || [ "${TEST_TYPE}" == "unit" ]; then
        cp *.xml /results
    fi
}

sed -i '/pyramid_debugtoolbar/d' setup.py
sed -i '/pyramid_debugtoolbar/d' devel/development.ini.example

cp devel/development.ini.example development.ini

/usr/bin/python2 setup.py develop || fail
py3_version=$(python3 -c "import sys ; print(sys.version[:3])")
mkdir -p /usr/local/lib/python$py3_version/site-packages/
/usr/bin/python3 setup.py develop || fail

if [ -z "${TEST_TYPE}" ] || [ "${TEST_TYPE}" == "flake8" ]; then
    flake8 || fail
fi
if [ -z "${TEST_TYPE}" ] || [ "${TEST_TYPE}" == "pydocstyle" ]; then
    pydocstyle bodhi || fail
fi
if [ -z "${TEST_TYPE}" ] || [ "${TEST_TYPE}" == "docs" ]; then
    make -C docs clean || fail
    make -C docs html || fail
    make -C docs man || fail
fi

if [ -z "${TEST_TYPE}" ] || [ "${TEST_TYPE}" == "unit" ]; then
    # The pip container calls it py.test but the Fedora container calls it py.test-2.
    if ! rpm -q python3-fedmsg; then
        /usr/bin/py.test $@ || (gather_results; fail)
    else
        /usr/bin/py.test-2 $@ || (gather_results; fail)
    fi
    # Since we don't have as much coverage with Python 3 yet, let's check out diff coverage against the
    # Python 2 results.
    diff-cover coverage.xml --compare-branch=origin/develop --fail-under=100 || fail

    # Since we skip some tests in Python 3, we don't reach the usually required coverage yet.
    sed -i "s/fail_under.*/fail_under = 78/" .coveragerc
    # The pip container puts the python 3 pytest into /usr/local/bin.
    if ! rpm -q python3-fedmsg; then
        /usr/local/bin/py.test $@ || (gather_results; fail)
    else
        /usr/bin/py.test-3 $@ || (gather_results; fail)
    fi
fi

gather_results
