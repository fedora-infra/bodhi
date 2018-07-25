# .bashrc

# Source global definitions
if [ -f /etc/bashrc ]; then
        . /etc/bashrc
fi

# Uncomment the following line if you don't like systemctl's auto-paging feature:
# export SYSTEMD_PAGER=

shopt -s expand_aliases
alias bci="sudo dnf install -y docker parallel && sudo systemctl enable docker && sudo systemctl start docker && sudo devel/run_tests.sh $@"
alias bdiff-cover="btest; diff-cover /home/vagrant/bodhi/coverage.xml --compare-branch=develop --fail-under=100"
alias bdocs="make -C /home/vagrant/bodhi/docs clean && make -C /home/vagrant/bodhi/docs html && make -C /home/vagrant/bodhi/docs man"
alias blog="sudo journalctl -u bodhi"
alias brestart="sudo systemctl restart bodhi && echo 'The Application is running on http://localhost:6543'"
alias bshell="pshell /home/vagrant/bodhi/development.ini"
alias bstart="sudo systemctl start bodhi && echo 'The Application is running on http://localhost:6543'"
alias bstop="sudo systemctl stop bodhi"
alias bteststyle="flake8-2 && pydocstyle bodhi"
alias bfedmsg="sudo journalctl -u fedmsg-tail"


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
    bteststyle && bdocs && py.test-2 $@ /home/vagrant/bodhi/ && py.test-3 $@ /home/vagrant/bodhi/
}

export BODHI_URL="http://localhost:6543/"
export PYTHONWARNINGS="once"

cd /home/vagrant/bodhi
