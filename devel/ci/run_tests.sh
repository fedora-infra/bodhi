#!/usr/bin/bash -ex
# This script is used to run the tests in the CI infrastructure, and launches a variety of parallel
# containers to test Bodhi across supported Fedora releases (See the RELEASES variable below).
# You can pass a -x flag to it to get it to exit early if a build or test run fails.

RELEASES="f25 f26 f27 rawhide pip"

if [[ $@ == *"-x"* ]]; then
    FAILFAST="--halt now,fail=1"
    PYTEST_ARGS="-x"
else
    FAILFAST=""
    PYTEST_ARGS=""
fi
FAILFAST="--halt now,fail=1"
PYTEST_ARGS="-x"

PARALLEL="parallel -v $FAILFAST --tag"

gather_results() {
    # Move the test results from the container-specific folders into the top test_results folder.
    $PARALLEL mv $(pwd)/test_results/{}/coverage.xml coverage-{}.xml ::: $RELEASES
    $PARALLEL mv $(pwd)/test_results/{}/nosetests.xml nosetests-{}.xml ::: $RELEASES
    $PARALLEL mv $(pwd)/test_results/{}/docs docs-{} ::: $RELEASES
}

sudo yum install -y epel-release
sudo yum install -y docker parallel

sudo systemctl start docker

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
$PARALLEL sudo docker build --pull -t test/{} -f devel/ci/Dockerfile-{} . ::: $RELEASES

# Make individual folders for each release to drop its test results and docs.
$PARALLEL mkdir -p $(pwd)/test_results/{} ::: $RELEASES
# Run the tests.
$PARALLEL sudo docker run --rm -v $(pwd)/test_results/{}:/results:z test/{} /bodhi/devel/ci/run_tests_fedora.sh $PYTEST_ARGS ::: $RELEASES || (gather_results; exit 1)
gather_results
