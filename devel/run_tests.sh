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

# This script is used to run the tests in a variety of parallel
# containers to test Bodhi across supported Fedora releases (See the RELEASES variable below). You
# can set the RELEASES environment variable to override the RELEASES for a given test run if you
# like. You can pass a -x flag to it to get it to exit early if a build or test run fails.
# It is intended to be run with sudo, since it needs to use docker.

BUILD_PARALLEL=${BUILD_PARALLEL:=""}
RELEASES=${RELEASES:="f26 f27 rawhide pip"}

if [[ $@ == *"-x"* ]]; then
    FAILFAST="--halt now,fail=1"
    PYTEST_ARGS="-x"
else
    FAILFAST=""
    PYTEST_ARGS=""
fi

PARALLEL="parallel -v $FAILFAST --tag"


tar_results() {
    tar cjf test_results.tar.bz2 test_results/
    mv test_results.tar.bz2 test_results/
}


# Assemble the Dockerfile snippets into Dockerfiles for each release.
pushd devel/ci/
for r in $RELEASES; do
    cat Dockerfile-header > Dockerfile-$r
    if [ $r != "pip" ]; then
        # Add the common rpm packages for the non-pip releases.
        cat rpm-packages >> Dockerfile-$r
    else
        # Let's use F26 for the pip tests.
        sed -i "s/FEDORA_RELEASE/27/" Dockerfile-$r
    fi
    cat $r-packages Dockerfile-footer >> Dockerfile-$r
    echo "COPY . /bodhi" >> Dockerfile-$r
    echo "RUN find /bodhi -name \"*.pyc\" -delete" >> Dockerfile-$r
    echo "RUN find /bodhi -name \"*__pycache__\" -delete" >> Dockerfile-$r
    echo "RUN rm -rf *.egg-info" >> Dockerfile-$r
    echo "RUN rm -rf .tox" >> Dockerfile-$r
done
popd

# Insert the container tag to pull for each release. There's a substitution in the parallel {}'s
# that will remove the "f" from the releases since Fedora uses just the number of the release in its
# tags.
$PARALLEL sed -i "s/FEDORA_RELEASE/{= s:f:: =}/" devel/ci/Dockerfile-{} ::: $RELEASES
# Build the containers.
$PARALLEL $BUILD_PARALLEL "docker build --pull -t test/{} -f devel/ci/Dockerfile-{} . || (echo \"JENKIES FAIL\"; exit 1)" ::: $RELEASES || (echo -e "\n\n\033[0;31mFAILED TO BUILD IMAGE(S)\033[0m\n\n"; exit 1)

# Make individual folders for each release to drop its test results and docs.
$PARALLEL mkdir -p $(pwd)/test_results/{} ::: $RELEASES
# Run the tests.
$PARALLEL docker run --rm -v $(pwd)/test_results/{}:/results:z test/{} /bodhi/devel/test_container.sh $PYTEST_ARGS ::: $RELEASES || (tar_results; echo -e "\n\n\033[0;31mTESTS FAILED\033[0m\n\n"; exit 1)
tar_results
echo -e "\n\n\033[0;32mSUCCESS!\033[0m\n\n"
