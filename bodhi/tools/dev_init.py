#!/usr/bin/env python
# $Id: $

"""
Bodhi developer initialization.

This script will populate your bodhi instance with sample releases, updates,
comments, etc.
"""

from datetime import datetime
from turbogears.database import PackageHub
from bodhi.tools.init import load_config
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

if __name__ == '__main__':
    main()
