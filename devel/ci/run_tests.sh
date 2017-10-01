#!/usr/bin/bash -ex

RELEASES="f25 f26 f27 rawhide"

gather_results() {
    # Move the test results from the container-specific folders into the top test_results folder.
    parallel -v mv $(pwd)/test_results/{}/coverage.xml coverage-{}.xml ::: $RELEASES
    parallel -v mv $(pwd)/test_results/{}/nosetests.xml nosetests-{}.xml ::: $RELEASES
    parallel -v mv $(pwd)/test_results/{}/docs docs-{} ::: $RELEASES
}

sudo yum install -y epel-release
sudo yum install -y docker parallel

sudo systemctl start docker

# Assemble the Dockerfile snippets into Dockerfiles for each release.
pushd devel/ci/
for r in $RELEASES; do
    cat Dockerfile-header $r-packages Dockerfile-footer > Dockerfile-$r
done
popd

# Insert the container tag to pull for each release. There's a substitution in the parallel {}'s
# that will remove the "f" from the releases since Fedora uses just the number of the release in its
# tags.
parallel -v sed -i "s/FEDORA_RELEASE/{= s:f:: =}/" devel/ci/Dockerfile-{} ::: $RELEASES
# Build the containers.
parallel -v sudo docker build -t test/{} -f devel/ci/Dockerfile-{} . ::: $RELEASES

# Make individual folders for each release to drop its test results and docs.
parallel -v mkdir -p $(pwd)/test_results/{} ::: $RELEASES
# Run the tests.
parallel -v sudo docker run --rm -v $(pwd)/test_results/{}:/results:z test/{} ::: $RELEASES || (gather_results; exit 1)
gather_results

# Run the tests on the EL 7 host.
./devel/ci/run_tests_el7.sh
