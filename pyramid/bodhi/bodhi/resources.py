import logging

from sqlalchemy.orm.exc import NoResultFound

from bodhi.models import initialize_sql, DBSession
from bodhi.models import Update, Package, Build, Release, User

log = logging.getLogger(__name__)

resources = {}

class BodhiRoot(object):
    __name__ = None
    __parent__ = None

    def __getitem__(self, key):
        resource = resources[key]()
        resource.__parent__ = self
        resource.__name__ = key
        return resource

    def get(self, key, default=None):
        try:
            item = self.__getitem__(key)
        except KeyError:
            item = default
        return item

    def __iter__(self):
        session = DBSession()
        query = session.query(self.__model__)
        return iter(query)


class BodhiResource(object):
    __name__ = None
    __parent__ = None
    __model__ = None
    __column__ = None

    def __getitem__(self, key):
        session = DBSession()
        log.debug('%s(%r)'% (self.__class__.__name__, key))
        try:
            return session.query(self.__model__).filter_by(**{self.__column__: key}).one()
        except NoResultFound:
            log.debug('NoResultsFound')
            raise KeyError(key)

    def get(self, key, default=None):
        try:
            item = self.__getitem__(key)
        except KeyError:
            item = default
        return item

    def __iter__(self):
        session = DBSession()
        query = session.query(self.__model__)
        return iter(query)


class PackageResource(BodhiResource):
    __model__ = Package
    __column__ = u'name'

class BuildResource(BodhiResource):
    __model__ = Build
    __column__ = u'nvr'

class UpdateResource(BodhiResource):
    __model__ = Update
    __column__ = u'title'

class ReleaseResource(BodhiResource):
    __model__ = Release
    __column__ = u'name'

class UserResource(BodhiResource):
    __model__ = User
    __keys__ = u'name'

root = BodhiRoot()

def default_get_root(request):
    global resources
    resources.update({
        u'updates': UpdateResource,
        u'builds':  BuildResource,
        u'packages': PackageResource,
        u'releases': ReleaseResource,
        #'users': UserResource,
        })
    return root

def appmaker(engine):
    initialize_sql(engine)
    return default_get_root
