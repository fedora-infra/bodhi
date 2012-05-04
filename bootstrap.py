#!/usr/bin/env python

import subprocess
import commands
import shutil
import sys
import os

ENVS = os.path.expanduser('~/.virtualenvs')
VENV = 'bodhi'


def _link_system_lib(lib):
    for libdir in ('lib', 'lib64'):
        location = '{libdir}/python{major}.{minor}/site-packages'.format(
            major=sys.version_info.major, minor=sys.version_info.minor,
            libdir=libdir)
        if not os.path.exists(os.path.join('/usr', location, lib)):
            if os.path.exists(os.path.join('/usr', location, lib + '.so')):
                lib += '.so'
            elif os.path.exists(os.path.join('/usr', location, lib + '.py')):
                lib += '.py'
            else:
                continue
        template = 'ln -s /usr/{location}/{lib} {workon}/{venv}/{location}/'
        print("Linking in global module: %s" % lib)
        cmd = template.format(
            location=location, venv=VENV, lib=lib,
            workon=os.getenv("WORKON_HOME"))
        status, output = commands.getstatusoutput(cmd)
        return status == 0 or status == 256  # File already linked.
    print("Cannot find global module %s" % lib)


def link_system_libs():
    for mod in ('koji', 'rpm', 'OpenSSL', 'urlgrabber', 'pycurl', 'yum',
                'rpmUtils', 'sqlitecachec', '_sqlitecache', 'psycopg2'):
        _link_system_lib(mod)


def _do_virtualenvwrapper_command(cmd):
    """ This is tricky, because all virtualenwrapper commands are
    actually bash functions, so we can't call them like we would
    other executables.
    """
    print "Trying '%s'" % cmd
    out, err = subprocess.Popen(
        ['bash', '-c', '. /usr/bin/virtualenvwrapper.sh; %s' % cmd],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).communicate()
    print out
    print err


def rebuild():
    """ Completely destroy and rebuild the virtualenv. """
    try:
        _do_virtualenvwrapper_command('rmvirtualenv %s' % VENV)
    except Exception as e:
        print str(e)

    cmd = 'mkvirtualenv --no-site-packages %s' % VENV
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


if __name__ == '__main__':
    print("Bootstrapping bodhi...")
    rebuild()
    link_system_libs()
