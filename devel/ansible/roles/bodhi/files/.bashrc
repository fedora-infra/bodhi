# .bashrc

# Source global definitions
if [ -f /etc/bashrc ]; then
        . /etc/bashrc
fi

# Uncomment the following line if you don't like systemctl's auto-paging feature:
# export SYSTEMD_PAGER=
source /srv/venv/bin/activate

shopt -s expand_aliases
alias bci="sudo -E /home/vagrant/bodhi/devel/ci/bodhi-ci"
alias bdocs="make -C /home/vagrant/bodhi/docs clean && make -C /home/vagrant/bodhi/docs html && make -C /home/vagrant/bodhi/docs man"
alias blog="sudo journalctl -u bodhi -u fm-consumer@config"
alias brestart="sudo systemctl restart bodhi && sudo systemctl restart fm-consumer@config && echo 'The Application is running on https://bodhi-dev.example.com'"
alias bstart="sudo systemctl start bodhi && sudo systemctl start fm-consumer@config && echo 'The Application is running on https://bodhi-dev.example.com'"
alias bstop="sudo systemctl stop bodhi && sudo systemctl stop fm-consumer@config"
alias blint="pre-commit run -a"
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
    blint || return $?
    bdocs || return $?
    for module in bodhi-messages bodhi-client bodhi-server; do
        pushd $module
        python -m pytest $@ tests || return $?
        popd
    done
    diff-cover bodhi-*/coverage.xml --compare-branch=develop --fail-under=100
}


function bstartdeps {
    pushd /tmp;
    curl -o waiverdb.dump.xz https://infrastructure.fedoraproject.org/infra/db-dumps/waiverdb.dump.xz
    xz -d --keep --force waiverdb.dump.xz
    popd;
    pushd /home/vagrant/bodhi/devel/docker/settings/policies/;
    curl -o fedora_tmpl.yaml https://pagure.io/fedora-infra/ansible/raw/master/f/roles/openshift-apps/greenwave/templates/fedora.yaml;
    jinja2 --format=yaml -o fedora.yaml fedora_tmpl.yaml
    rm fedora_tmpl.yaml
    popd;
    sudo docker-compose -f /home/vagrant/bodhi/devel/docker/compose-services.yml up -d
}

alias bstopdeps="sudo docker-compose -f /home/vagrant/bodhi/devel/docker/compose-services.yml stop"

function bremovedeps {
    sudo docker-compose -f /home/vagrant/bodhi/devel/docker/compose-services.yml down --rmi all -v
    rm -f /tmp/waiverdb.dump*
    rm -f /home/vagrant/bodhi/devel/docker/settings/policies/*
}

export BODHI_URL="https://bodhi-dev.example.com/"
export BODHI_OPENID_PROVIDER="https://ipsilon.tinystage.test/idp/"
export PYTHONWARNINGS="once"
export BODHI_CI_ARCHIVE_PATH="/home/vagrant/bodhi-ci-test_results/"

cd /home/vagrant/bodhi
