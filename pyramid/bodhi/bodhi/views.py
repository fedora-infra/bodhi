#from pyramid.view import view_config
from pyramid.response import Response

from bodhi.models import Update, Package, Build, Release, DBSession

def view_model_instance(context, request):
    return {'context': context.__json__()}

def view_model(context, request):
    print "view_model(%s)" % context
    session = DBSession()
    # TODO: pagination
    entries = session.query(context.__model__).all()
    return {'entries': [entry.__json__() for entry in entries]}
