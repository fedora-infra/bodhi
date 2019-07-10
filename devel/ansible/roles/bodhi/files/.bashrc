# .bashrc

# Source global definitions
if [ -f /etc/bashrc ]; then
        . /etc/bashrc
fi

# Uncomment the following line if you don't like systemctl's auto-paging feature:
# export SYSTEMD_PAGER=

shopt -s expand_aliases
alias bci="sudo -E /home/vagrant/bodhi/devel/ci/bodhi-ci"
alias bdocs="make -C /home/vagrant/bodhi/docs clean && make -C /home/vagrant/bodhi/docs html && make -C /home/vagrant/bodhi/docs man"
alias blog="sudo journalctl -u bodhi -u fm-consumer@config"
alias brestart="sudo systemctl restart bodhi && sudo systemctl restart fm-consumer@config && echo 'The Application is running on http://localhost:6543'"
alias bstart="sudo systemctl start bodhi && sudo systemctl start fm-consumer@config && echo 'The Application is running on http://localhost:6543'"
alias bstop="sudo systemctl stop bodhi && sudo systemctl stop fm-consumer@config"
alias blint="flake8-3 && pydocstyle bodhi && mypy"
alias bmessages="sudo journalctl -u print-messages"


function bresetdb {
    bstop;
    sudo runuser -l postgres -c "psql -c \"DROP DATABASE bodhi2\"";
    sudo runuser -l postgres -c 'createdb bodhi2';
    xzcat /tmp/bodhi2.dump.xz | sudo runuser -l postgres -c 'psql bodhi2';
    pushd /home/vagrant/bodhi;
    alembic upgrade head;
    popd;
    bstart;
}


function btest {
    find /home/vagrant/bodhi -name "*.pyc" -delete;
    blint && bdocs && py.test-3 $@ /home/vagrant/bodhi/bodhi/tests && diff-cover /home/vagrant/bodhi/coverage.xml --compare-branch=develop --fail-under=100
}

export BODHI_URL="http://localhost:6543/"
export BODHI_OPENID_API="https://id.stg.fedoraproject.org/api/v1/"
export PYTHONWARNINGS="once"
export BODHI_CI_ARCHIVE_PATH="/home/vagrant/bodhi-ci-test_results/"

cd /home/vagrant/bodhi
