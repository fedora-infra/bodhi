#!/usr/bin/env python

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

""" This script can bootstrap either a python2 or a python3 environment.

The environments it generates are named by the python version they are built
against.  i.e.:  bodhi-python2.7 or bodhi-python3.2.
To generate one or the other, just use the relevant python binary.  For a
python2 env, run::

    python2 bootstrap.py

And for a python3 env, run::

    python3 bootstrap.py
"""

import subprocess
import shutil
import glob
import sys
import os

ENVS = os.path.expanduser('~/.virtualenvs')
VENV = 'bodhi-python{major}.{minor}'.format(
    major=sys.version_info[0],
    minor=sys.version_info[1],
)

VENVWRAPPER = os.path.exists('/usr/bin/virtualenvwrapper.sh')
if not VENVWRAPPER:
    ENVS = os.getcwd()


if "check_output" not in dir( subprocess ): # duck punch it in!
    def f(*popenargs, **kwargs):
        if 'stdout' in kwargs:
            raise ValueError('stdout argument not allowed, it will be overridden.')
        process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
        output, unused_err = process.communicate()
        retcode = process.poll()
        if retcode:
            cmd = kwargs.get("args")
            if cmd is None:
                cmd = popenargs[0]
            raise subprocess.CalledProcessError(retcode, cmd)
        return output
    subprocess.check_output = f


def _link_system_lib(lib):
    workon = '.'
    if VENVWRAPPER:
        workon=os.getenv("WORKON_HOME")
    for libdir in ('lib', 'lib64'):
        location = '{libdir}/python{major}.{minor}/site-packages'.format(
            major=sys.version_info[0], minor=sys.version_info[1],
            libdir=libdir)
        if not os.path.exists(os.path.join('/usr', location, lib)):
            if os.path.exists(os.path.join('/usr', location, lib + '.so')):
                lib += '.so'
            elif os.path.exists(os.path.join('/usr', location, lib + '.py')):
                lib += '.py'
            else:
                continue

        template = 'ln -s /usr/{location}/{lib} {workon}/{venv}/{location}/'

        # Link in the egg-info for Pillow
        if lib == 'PIL':
            egginfo = glob.glob(os.path.join('/usr', location, 'Pillow-*.egg-info'))
            if egginfo:
                print("Linking in Pillow egg-info")
                cmd = template.format(
                    location=location, venv=VENV, lib=os.path.basename(egginfo[0]), workon=workon)
                try:
                    subprocess.check_output(cmd.split())
                except subprocess.CalledProcessError as e:
                    # File already linked.
                    return e.returncode == 256

        print("Linking in global module: %s" % lib)
        cmd = template.format(
            location=location, venv=VENV, lib=lib, workon=workon)
        try:
            subprocess.check_output(cmd.split())
            return True
        except subprocess.CalledProcessError as e:
            # File already linked.
            return e.returncode == 256

    print("Cannot find global module %s" % lib)


def link_system_libs():
    for mod in ('koji', 'rpm', 'OpenSSL', 'urlgrabber', 'pycurl',
                'rpmUtils', 'sqlitecachec', '_sqlitecache', 'psycopg2',
                'krbVmodule', 'deltarpm', '_deltarpmmodule',
                'fedora_cert', 'libxml2', 'libxml2mod', 'librepo', 'createrepo_c',
                'dnf', 'libcomps', 'gpgme', 'lzma', 'iniparse', 'hawkey',
                'yum'):
        _link_system_lib(mod)


def _do_virtualenvwrapper_command(cmd):
    """ This is tricky, because all virtualenwrapper commands are
    actually bash functions, so we can't call them like we would
    other executables.
    """
    print("Trying '%s'" % cmd)
    cmds = cmd.split(' ')
    if VENVWRAPPER:
        cmds = ['bash', '-c', '. /usr/bin/virtualenvwrapper.sh; %s' % cmd]
    out, err = subprocess.Popen(
        cmds, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).communicate()
    print(out)
    print(err)


def rebuild():
    """ Completely destroy and rebuild the virtualenv. """
    try:
        cmd = 'rm -rf %s' % VENV
        if VENVWRAPPER:
            cmd = 'rmvirtualenv %s' % VENV
        _do_virtualenvwrapper_command(cmd)
    except Exception as e:
        print(unicode(e))

    cmd = 'virtualenv --no-site-packages -p /usr/bin/python{major}.{minor} {v}'\
            .format(
                major=sys.version_info[0],
                minor=sys.version_info[1],
                v=VENV,
            )
    if VENVWRAPPER:
        cmd = 'mkvirtualenv --no-site-packages -p /usr/bin/python{major}.{minor} {v}'\
            .format(
                major=sys.version_info[0],
                minor=sys.version_info[1],
                v=VENV,
            )
    _do_virtualenvwrapper_command(cmd)

    # Do two things here:
    #  - remove all *.pyc that exist in srcdir.
    #  - remove all data/templates dirs that exist (mako caches).
    for base, dirs, files in os.walk(os.getcwd()):
        for fname in files:
            if fname.endswith(".pyc"):
                os.remove(os.path.sep.join([base, fname]))

        if base.endswith('data/templates'):
            shutil.rmtree(base)


def setup_develop():
    """ `python setup.py develop` in our virtualenv """
    workon = '.'
    if VENVWRAPPER:
        workon=os.getenv("WORKON_HOME")
    cmd = '{workon}/{env}/bin/python setup.py develop'.format(
        envs=ENVS, env=VENV, workon=workon)
    print(cmd)
    subprocess.call(cmd.split())


def install_test_deps():
    """
    To work around `python setup.py test` downloadling egg files to the current
    directory
    """
    workon = '.'
    if VENVWRAPPER:
        workon=os.getenv("WORKON_HOME")
    cmd = '{workon}/{env}/bin/pip install nose-cov webtest mock'.format(
        envs=ENVS, env=VENV, workon=workon)
    print(cmd)
    subprocess.call(cmd.split())


if __name__ == '__main__':
    print("Bootstrapping bodhi...")
    rebuild()
    # TODO - yum install
    #   - pcaro-hermit
    #   - freetype-devel
    #   - libjpeg-turbo-devel
    link_system_libs()
    setup_develop()
    install_test_deps()
