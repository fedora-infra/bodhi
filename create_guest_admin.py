#!/usr/bin/env python
from init import load_config
from bodhi.model import User, Group
from turbogears.database import PackageHub

hub = PackageHub("bodhi")
__connection__ = hub

load_config()

hub.begin()
print "Creating guest user and giving it administrator priviliges"
guest = User(user_name='guest')
guest.password = 'guest'
admin = Group(group_name='admin', display_name='Bodhi administrators')
guest.addGroup(admin)
hub.commit()
print "Done!"
