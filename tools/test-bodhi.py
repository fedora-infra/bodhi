#!/usr/bin/python -tt
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# Authors: Tim Lauridsen <timlau@fedoraproject.org>

import os

PKG = 'yumex-2.0.1-2.fc7' # This package is a test build i have made in Koji
BODHI = './bodhi.py'
IMPORT_FILE  = 'bodhi-test-import'

def make_import_file(typ,cve=False):
    f = open(IMPORT_FILE,'w')
    f.write(': Bodhi update template, all entries starting with a : are ignored\n')
    f.write('::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::\n')
    f.write(':\n')
    f.write(': Select a type: S=Security, B=Bugfix, E=Enhancement\n')
    f.write(':\n')
    f.write('TYPE=%s\n' % typ)
    f.write(': Select Bug numbers to include or add you own\n')
    f.write(': You can either use multiple BUG= statements or separate the bug numbers with a space\n')
    f.write('BUG=282141\n') # This is a existing yumex bug, created for this test
    f.write(': Select CVE numbers to include or add you own\n')
    f.write(': You can either use multiple CVE= statements or separate the cve numbers with a space\n')
    if cve:
        f.write('CVE=CVE-2344-333\n')
    f.write(':\n')
    f.write(': Now edit the update notification message, everything that does not start with a : or\n')
    f.write(': CVE=, TYPE= or BUG= will be used\n')
    f.write('This is a yumex test update used to testing\n')
    f.write('The Bodhi commandline client\n')
    f.close
    
def run(cmd,msg):    
    print '============================================================================'
    print msg
    print "Running : %s \n" % cmd
    print '--> Output start'
    os.system(cmd)
    print '--> Output End'
    print '\n'


if __name__ == "__main__":
    # Cleanup
    cmd = BODHI+" -d "+ PKG 
    run(cmd,"Make sure the update dont exist ")
    # Test update creation
    make_import_file('B')
    cmd = BODHI+" -n "+ PKG + ' --file='+IMPORT_FILE
    run(cmd,"Create an update (BUGFIX) ")
    run(cmd,"Create an update there already exist (Should fail) ")
    # Test push to testing
    cmd = BODHI+" -T "+ PKG 
    run(cmd,"Push the update to testing ")
    run(cmd,"Push the update to testing again (Should fail) ")
    cmd = BODHI+" -S "+ PKG 
    run(cmd,"Push the update to stable (Should fail because it has a pending push) ")
    # Cleanup
    cmd = BODHI+" -d "+ PKG 
    run(cmd,"Make sure the update dont exist ")
    # Test update creation (Security)
    make_import_file('S',cve = True)
    cmd = BODHI+" -n "+ PKG + ' --file='+IMPORT_FILE
    run(cmd,"Create an update (SECURITY) ")
    # Test push to testing
    cmd = BODHI+" -T "+ PKG 
    run(cmd,"Push the update to testing (It should go direct to stable, insted of testing  ")
    