#!/usr/bin/bash -ex
# This script is used to run the tests in the CI infrastructure, and launches a variety of parallel
# containers to test Bodhi across supported Fedora releases.


sudo yum install -y epel-release
sudo yum install -y bzip2 docker parallel

sudo systemctl start docker

./devel/run_tests.sh
