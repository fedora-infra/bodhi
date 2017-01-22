# .bashrc

# Source global definitions
if [ -f /etc/bashrc ]; then
        . /etc/bashrc
fi

# Uncomment the following line if you don't like systemctl's auto-paging feature:
# export SYSTEMD_PAGER=

shopt -s expand_aliases
alias bdocs="pushd /home/vagrant/bodhi/docs && make html; popd"
alias blog="sudo journalctl -u bodhi"
alias brestart="sudo systemctl restart bodhi"
alias bstart="sudo systemctl start bodhi"
alias bstop="sudo systemctl stop bodhi"

function btest {
    pushd /home/vagrant/bodhi && python setup.py nosetests $@; popd
}
