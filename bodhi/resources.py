import logging

from sqlalchemy.orm.exc import NoResultFound

from bodhi.models import DBSession
from bodhi.models import Update, Package, Build, Release, User, Bug, Comment
from bodhi.widgets import NewUpdateForm

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


class BodhiResource(object):
    __name__ = None
    __parent__ = None
    __model__ = None
    __column__ = None
    __filter__ = None

    def __getitem__(self, key):
        session = DBSession()
        if self.__filter__:
            try:
                key = self.__filter__(key)
            except:
                raise KeyError(key)
        try:
            return session.query(self.__model__).filter_by(
                    **{self.__column__: key}).one()
        except NoResultFound:
            raise KeyError(key)


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
    __column__ = u'name'


class BugResource(BodhiResource):
    __model__ = Bug
    __column__ = u'bug_id'
    __filter__ = int


class CommentResource(BodhiResource):
    __model__ = Comment
    __column__ = u'id'
    __filter__ = int

root = BodhiRoot()


def default_get_root(request):
    global resources
    resources.update({
        u'updates': UpdateResource,
        u'builds':  BuildResource,
        u'packages': PackageResource,
        u'releases': ReleaseResource,
        u'comments': CommentResource,
        u'users': UserResource,
        u'bugs': BugResource,
        u'new': lambda: NewUpdateForm.req(),
        })
    return root


def appmaker(engine):
    return default_get_root
