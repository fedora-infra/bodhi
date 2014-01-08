bodhi v2.0
==========

Setup virtualenvwrapper
-----------------------
``sudo yum -y install python-virtualenvwrapper``

Add the following to your `~/.bashrc`::

    export WORKON_HOME=$HOME/.virtualenvs
    source /usr/bin/virtualenvwrapper.sh

Bootstrap the virtualenv
------------------------
::

    ./bootstrap.py
    workon bodhi-python2.7

Run the test suite
------------------
``python setup.py test``

Initialize the database
-----------------------
``initialize_bodhi_db``

Migrating Bodhi from v1.0 to v2.0
---------------------------------
::

    curl -O https://fedorahosted.org/releases/b/o/bodhi/bodhi-pickledb.tar.bz2
    tar -jxvf bodhi-pickledb.tar.bz2
    rm bodhi-pickledb.tar.bz2
    PYTHONPATH=$(pwd) python tools/pickledb.py migrate bodhi-pickledb*

Run the web app
---------------
``pserve development.ini``
