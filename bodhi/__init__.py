from sqlalchemy import engine_from_config

from pyramid.decorator import reify
from pyramid.request import Request
from pyramid.security import unauthenticated_userid
from pyramid.config import Configurator

from bodhi.resources import appmaker

#class BodhiRequest(Request):
#    @reify
#    def user(self):
#        # <your database connection, however you get it, the below line
#        # is just an example>
#        dbconn = self.registry.settings['dbconn']
#        userid = unauthenticated_userid(self)
#        if userid is not None:
#            # this should return None if the user doesn't exist
#            # in the database
#            return dbconn['users'].query({'id':userid})


def main(global_config, **settings):
    """ This function returns a WSGI application """
    engine = engine_from_config(settings, 'sqlalchemy.')
    get_root = appmaker(engine)
    config = Configurator(settings=settings, root_factory=get_root)
    #config.set_request_factory(BodhiRequest)
    config.add_static_view('static', 'bodhi:static')

    # JSON views
    config.add_view('bodhi.views.view_model_instance_json',
                    context='bodhi.models.Base',
                    accept='application/json',
                    renderer='json')
    config.add_view('bodhi.views.view_model_json',
                    context='bodhi.resources.BodhiResource',
                    accept='application/json',
                    renderer='json')

    # Mako template views
    config.add_view('bodhi.views.view_model_instance',
                    context='bodhi.models.Base',
                    accept='text/html',
                    renderer='bodhi:templates/instance.mak')
    config.add_view('bodhi.views.view_model',
                    accept='text/html',
                    context='bodhi.resources.BodhiResource',
                    renderer='bodhi:templates/model.mak')

    # Widget data providers
    widget_view = lambda context, request: context.request(request)
    config.add_view(view=widget_view, context='tw2.core.widgets.WidgetMeta')

    return config.make_wsgi_app()
