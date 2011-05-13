from sqlalchemy import engine_from_config

from pyramid.decorator import reify
from pyramid.request import Request
from pyramid.security import unauthenticated_userid
from pyramid.config import Configurator

from bodhi.resources import appmaker

class BodhiRequest(Request):
    @reify
    def user(self):
        # <your database connection, however you get it, the below line
        # is just an example>
        dbconn = self.registry.settings['dbconn']
        userid = unauthenticated_userid(self)
        if userid is not None:
            # this should return None if the user doesn't exist
            # in the database
            return dbconn['users'].query({'id':userid})


def main(global_config, **settings):
    """ This function returns a WSGI application """
    engine = engine_from_config(settings, 'sqlalchemy.')
    get_root = appmaker(engine)
    config = Configurator(settings=settings, root_factory=get_root)
    #config.set_request_factory(BodhiRequest)
    config.add_static_view('static', 'bodhi:static')

    config.add_view('bodhi.views.view_model_instance',
                    context='bodhi.models.Base',
                    renderer='json')
    config.add_view('bodhi.views.view_model',
                    context='bodhi.resources.BodhiResource',
                    renderer='json')
    config.scan()
    return config.make_wsgi_app()
