#!/usr/bin/bash -ex

gather_results() {
    mv docs/_build/html /results/docs
    cp *.xml /results
}

sed -i '/pyramid_debugtoolbar/d' setup.py
sed -i '/pyramid_debugtoolbar/d' development.ini.example

cp development.ini.example development.ini

/usr/bin/python setup.py develop

/usr/bin/tox
/usr/bin/py.test || (gather_results; exit 1)

gather_results

diff-cover coverage.xml --compare-branch=origin/develop --fail-under=100
