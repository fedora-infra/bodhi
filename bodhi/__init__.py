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

    # Sessions
    #from pyramid_beaker import session_factory_from_settings
    #session_factory = session_factory_from_settings(settings)

    config = Configurator(settings=settings, root_factory=get_root)
                          #session_factory=session_factory)

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

    # FormAlchemy
    import bodhi.fainit
    config.include(bodhi.fainit)

    # register an admin UI
    #config.formalchemy_admin('admin', package='bodhi')
    #config.formalchemy_admin('/admin', package='bodhi', view='fa.jquery.pyramid.ModelView')
    #config.formalchemy_model('/admin', package='bodhi', model='bodhi.models.Update')

    # register an admin UI for a single model
    #config.formalchemy_model('foo', package='bodhi', model='bodhi.models.Foo')

    # register custom model listing
    #config.formalchemy_model_view('admin',
    #                              model='pyramidapp.models.Foo',
    #                              context='pyramid_formalchemy.resources.ModelListing',
    #                              renderer='templates/foolisting.pt',
    #                              attr='listing',
    #                              request_method='GET',
    #                              permission='view')

    # register custom model view
    #config.formalchemy_model_view('admin',
    #                              model='pyramidapp.models.Foo',
    #                              context='pyramid_formalchemy.resources.Model',
    #                              name='',
    #                              renderer='templates/fooshow.pt',
    #                              attr='show',
    #                              request_method='GET',
    #                              permission='view')

    return config.make_wsgi_app()
