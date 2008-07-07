#!/usr/bin/env python
# $Id: $

"""
Bodhi developer initialization.

This script will populate your bodhi instance with sample releases, updates,
comments, etc.
"""

from turbogears.database import PackageHub
from bodhi.util import load_config
from bodhi.exceptions import DuplicateEntryError
from bodhi.model import User, Group

hub = PackageHub("bodhi")
__connection__ = hub

def main():
    load_config()
    hub.begin()

    try:
        print "\nCreating guest user and giving it administrator priviliges"
        guest = User(user_name='guest', display_name='Bodhi Hacker')
        guest.password = 'guest'
        admin = Group(group_name='releng', display_name='Bodhi administrators')
        guest.addGroup(admin)
        hub.commit()
    except DuplicateEntryError:
        print "guest account already created"

if __name__ == '__main__':
    main()
