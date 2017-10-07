#!/usr/bin/bash -ex
# This script is used to run the tests in the CI infrastructure, and launches a variety of parallel
# containers to test Bodhi across supported Fedora releases (See the RELEASES variable below). You
# can set the RELEASES environment variable to override the RELEASES for a given test run if you
# like. You can pass a -x flag to it to get it to exit early if a build or test run fails.
# It is intended to be run with sudo, since it needs to use docker.

RELEASES=${RELEASES:="f25 f26 f27 rawhide pip"}

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
        sed -i "s/FEDORA_RELEASE/26/" Dockerfile-$r
    fi
    cat $r-packages Dockerfile-footer >> Dockerfile-$r
    echo "COPY . /bodhi" >> Dockerfile-$r
done
popd

# Insert the container tag to pull for each release. There's a substitution in the parallel {}'s
# that will remove the "f" from the releases since Fedora uses just the number of the release in its
# tags.
$PARALLEL sed -i "s/FEDORA_RELEASE/{= s:f:: =}/" devel/ci/Dockerfile-{} ::: $RELEASES
# Build the containers.
$PARALLEL docker build --pull -t test/{} -f devel/ci/Dockerfile-{} . ::: $RELEASES

# Make individual folders for each release to drop its test results and docs.
$PARALLEL mkdir -p $(pwd)/test_results/{} ::: $RELEASES
# Run the tests.
$PARALLEL docker run --rm -v $(pwd)/test_results/{}:/results:z test/{} /bodhi/devel/ci/run_tests_fedora.sh $PYTEST_ARGS ::: $RELEASES || (tar_results; exit 1)
tar_results
