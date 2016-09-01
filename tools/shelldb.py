"""
Used with the bodhi pshell.

    pshell /etc/bodhi/production.ini
    execfile('shelldb.py')
"""
from pyramid.paster import get_appsettings, setup_logging
from sqlalchemy import engine_from_config
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension
import transaction
config_uri = '/etc/bodhi/production.ini'
settings = get_appsettings(config_uri)
engine = engine_from_config(settings, 'sqlalchemy.')
Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Session.configure(bind=engine)
db = Session()

def delete_update(up):
        for b in up.builds:
                db.delete(b)
                if b.override:
                        db.delete(b.override)
        for c in up.comments:
                db.delete(c)
        db.delete(up)
