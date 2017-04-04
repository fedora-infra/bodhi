"""
Used with the bodhi pshell.

    pshell /etc/bodhi/production.ini
    execfile('shelldb.py')
"""
from pyramid.paster import get_appsettings
import sys

from bodhi.server import Session, initialize_db


config_uri = None
for arg in sys.argv:
    if arg.endswith('.ini'):
        config_uri = arg
if not config_uri:
    config_uri = '/etc/bodhi/production.ini'


settings = get_appsettings(config_uri)
initialize_db(settings)
db = Session()


def delete_update(up):
        for b in up.builds:
                db.delete(b)
                if b.override:
                        db.delete(b.override)
        for c in up.comments:
                db.delete(c)
        db.delete(up)
