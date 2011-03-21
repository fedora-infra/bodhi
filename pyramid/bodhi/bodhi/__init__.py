from pyramid.config import Configurator
from sqlalchemy import engine_from_config

from bodhi.models import appmaker

def main(global_config, **settings):
    """ This function returns a WSGI application """
    engine = engine_from_config(settings, 'sqlalchemy.')
    get_root = appmaker(engine)
    config = Configurator(settings=settings, root_factory=get_root)
    config.add_static_view('static', 'bodhi:static')
    config.add_view('bodhi.views.view_root', 
                    context='bodhi.models.Release', 
                    renderer="templates/root.pt")
    #config.add_view('bodhi.views.view_model',
    #                context='bodhi.models.MyModel',
    #                renderer="templates/model.pt")
    return config.make_wsgi_app()
