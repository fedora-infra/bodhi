#!/usr/bin/bash

# Run poetry install in all 3 modules

set -cex

LABEL="$1"
shift
MODULES=$@

for submodule in {" ".join(MODULES)}; do
    pushd $submodule;
      VERSION=( $(poetry version) );
      poetry build -f sdist;
      tar -xzvf "dist/${VERSION[0]}-${VERSION[1]}.tar.gz" -C /tmp/;
      pushd "/tmp/${VERSION[0]}-${VERSION[1]}";
        python3 setup.py develop;
      popd;
    popd;
done

if [[ "$LABEL" == 'docs' ]]; then
    make -C docs clean
    make -C docs html PYTHON=/usr/bin/python3
    make -C docs man PYTHON=/usr/bin/python3
    cp -rv docs/_build/* /results/
fi

# Run the tests in each submodule
if [[ "$LABEL" == 'unit' ]]; then
    for submodule in {modules}; do
        mkdir -p /results/$submodule;
        pushd $submodule;
          python3 -m pytest {pytest_flags};
          exitcode=$?;
          cp *.xml /results/$submodule/;
          test $exitcode -gt 0 && exit 1;
        popd;
    done
fi
