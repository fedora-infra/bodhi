bodhi v2.0
==========

Bootstrap the virtualenv
------------------------
sudo yum -y install python-virtualenvwrapper
./bootstrap.py
workon bodhi-python2.7
pip install kitchen
python setup.py develop

Run the test suite
------------------
python setup.py test

Initialize the database
-----------------------
pserve development.ini

Migrating Bodhi from v1.0 to v2.0
---------------------------------
PYTHONPATH=$(pwd) python tools/pickledb.py migrate bodhi-pickledb
