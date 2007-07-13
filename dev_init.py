#!/usr/bin/env python
# $Id: $

"""
Bodhi developer initialization.

This script will populate your bodhi instance with sample releases, updates,
comments, etc.
"""

from init import load_config
from datetime import datetime
from turbogears.database import PackageHub
from bodhi.exceptions import DuplicateEntryError
from bodhi.model import (User, Group, PackageUpdate, Package, Release,
                         PackageBuild, Bugzilla, Comment, CVE)

hub = PackageHub("bodhi")
__connection__ = hub

def main():
    load_config()
    hub.begin()

    try:
        print "Creating guest user and giving it administrator priviliges"
        guest = User(user_name='guest', display_name='Bodhi Hacker')
        guest.password = 'guest'
        admin = Group(group_name='releng', display_name='Bodhi administrators')
        guest.addGroup(admin)
        hub.commit()
    except DuplicateEntryError:
        print "guest account already created"

    print "Creating some fake updates/bugs/comments"
    print "Note: it's normal to see some errors below (not tracebacks)"

    package = Package(name='yum')
    build = PackageBuild(nvr='yum-3.2.1-1.fc7', package=package)
    update = PackageUpdate(title='yum-3.2.1-1.fc7', release=Release.select()[0],
                           submitter='bodhi', status='pending',
                           notes='This is a test update created by bodhi',
                           type='enhancement')
    update.addPackageBuild(build)

    package = Package(name='powertop')
    build = PackageBuild(nvr='powertop-1.7-3.fc7', package=package)
    update = PackageUpdate(title='powertop-1.7-3.fc7',
                           release=Release.select()[0],
                           submitter='guest', status='stable',
                           notes='Update to new powertop, with better '
                                 'reporting, more translations, suggestions '
                                 'for better battery life, and a crunchy candy'
                                 ' shell', 
                           type='enhancement', date_pushed=datetime.now(),
                           update_id='FEDORA-2007-0970')
    update.addPackageBuild(build)
    bug = Bugzilla(bz_id=246796)
    bug.title = 'Stack overflow detected when running powertop with de_DE.UTF-8 locale'
    update.addBugzilla(bug)
    comment = Comment(author='bodhi', text='Works great!', karma=1,
                      update=update)

    package = Package(name='hotwire')
    build = PackageBuild(nvr='hotwire-0.590-1.fc7', package=package)
    update = PackageUpdate(title='hotwire-0.590-1.fc7',
                           release=Release.select()[0],
                           submitter='walters', status='stable',
                           notes='New upstream version.',
                           pushed=True,
                           type='bugfix', date_pushed=datetime.now(),
                           update_id='FEDORA-2007-1042')
    update.addPackageBuild(build)
    comment = Comment(author='Bob Vila', text='Wooo!', karma=1,
                      update=update)

    package = Package(name='gimp')
    build = PackageBuild(nvr='gimp-2.2.16-2.fc7', package=package)
    update = PackageUpdate(title='gimp-2.2.16-2.fc7',
                           release=Release.select()[0],
                           submitter='nphilipp', status='stable',
                           pushed=True,
                           notes='New upstream version.',
                           type='security', date_pushed=datetime.now(),
                           update_id='FEDORA-2007-1044')
    update.addPackageBuild(build)
    bug = Bugzilla(bz_id=247566)
    bug.title = 'CVE-2006-4519 GIMP multiple image loader integer overflows [F7]'
    update.addBugzilla(bug)
    cve = CVE(cve_id='CVE-2006-4519')
    update.addCVE(cve)
    comment = Comment(author='ralf', text='OMGREGRESSION!1', karma=-1,
                      update=update)
    comment = Comment(author='Lloyd Christmas', text='WFM', karma=1,
                      update=update)

    package = Package(name='vim')
    build = PackageBuild(nvr='vim-7.1.12-1.fc7', package=package)
    update = PackageUpdate(title='vim-7.1.12-1.fc7',
                           release=Release.select()[0],
                           submitter='karsten', status='testing',
                           notes='update VIM to version 7.1 Patchlevel 12',
                           type='enhancement', date_pushed=datetime.now(),
                           update_id='FEDORA-2007-0718')
    update.addPackageBuild(build)
    comment = Comment(author='Bob Vila', text='plz2push to stable', karma=0,
                      update=update)

if __name__ == '__main__':
    main()
