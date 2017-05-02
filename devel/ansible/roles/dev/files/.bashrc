# .bashrc

# Source global definitions
if [ -f /etc/bashrc ]; then
        . /etc/bashrc
fi

# Uncomment the following line if you don't like systemctl's auto-paging feature:
# export SYSTEMD_PAGER=

shopt -s expand_aliases
alias bdocs="pushd /home/vagrant/bodhi/docs && make html && make man; popd"
alias blog="sudo journalctl -u bodhi"
alias brestart="sudo systemctl restart bodhi && echo 'The Application is running on http://localhost:6543'"
alias bshell="pshell /home/vagrant/bodhi/development.ini"
alias bstart="sudo systemctl start bodhi && echo 'The Application is running on http://localhost:6543'"
alias bstop="sudo systemctl stop bodhi"
alias bteststyle="pushd /home/vagrant/bodhi && nosetests -sx ~/bodhi/bodhi/tests/test_style.py; popd"

function btest {
    find /home/vagrant/bodhi -name "*.pyc" -delete;
    pushd /home/vagrant/bodhi && python setup.py nosetests $@; popd
}

export BODHI_URL="http://localhost:6543/"
export PYTHONWARNINGS="once"
