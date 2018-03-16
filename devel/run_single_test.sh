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

# This script is used to run the container tests against a single Fedora release. You
# can set the RELEASE environment variable to override the RELEASE for a given test run if you
# like. You can pass a -x flag to it to get it to exit early if a build or test run fails.
# It is intended to be run with sudo, since it needs to use docker.

RELEASE=${RELEASE:="f27"}

if [[ $@ == *"-x"* ]]; then
    FAILFAST="--halt now,fail=1"
    PYTEST_ARGS="-x"
else
    FAILFAST=""
    PYTEST_ARGS=""
fi


# Assemble the Dockerfile snippet into a Dockerfile
pushd devel/ci/
cat Dockerfile-header > Dockerfile-$RELEASE
if [ $RELEASE != "pip" ]; then
    # Add the common rpm packages for the non-pip releases.
    cat rpm-packages >> Dockerfile-$RELEASE
else
    # Let's use F26 for the pip tests.
    sed -i "s/FEDORA_RELEASE/27/" Dockerfile-$RELEASE
fi
cat $RELEASE-packages Dockerfile-footer >> Dockerfile-$RELEASE
echo "COPY . /bodhi" >> Dockerfile-$RELEASE
popd

# This will remove the "f" from the releases since Fedora uses just the number of the release in its
# tags.
RELNUM=$(echo $RELEASE | sed 's/^f//')
sed -i "s/FEDORA_RELEASE/$RELNUM/" devel/ci/Dockerfile-$RELEASE
# Build the containers.
docker build -t test/$RELEASE -f devel/ci/Dockerfile-$RELEASE .

# Run the tests.
docker run --rm test/$RELEASE /bodhi/devel/test_container.sh $PYTEST_ARGS
echo -e "\n\n\033[0;32mSUCCESS!\033[0m\n\n"
