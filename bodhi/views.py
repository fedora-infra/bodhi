from webhelpers.html.grid import Grid
from webhelpers.paginate import Page, PageURL_WebOb

from bodhi.models import DBSession
from bodhi.widgets import widgets

## JSON views

def view_model_instance_json(context, request):
    return {'context': context.__json__()}

def view_model_json(context, request):
    session = DBSession()
    entries = session.query(context.__model__)
    current_page = int(request.params.get('page', 1))
    items_per_page = int(request.params.get('items_per_page', 20))
    page = Page(entries, page=current_page, items_per_page=items_per_page)
    return {'entries': [entry.__json__() for entry in page]}

## Mako templated views

def view_model_instance(context, request):
    return {'context': context}

def view_model(context, request):
    session = DBSession()
    entries = session.query(context.__model__)
    current_page = int(request.params.get('page', 1))
    items_per_page = int(request.params.get('items_per_page', 20))
    page_url = PageURL_WebOb(request)
    page = Page(entries, page=current_page, url=page_url,
                items_per_page=items_per_page)
    grid = Grid([entry.__json__() for entry in page],
                context.__model__.grid_columns())

    #grid = widgets[context.__model__.__name__]
    return {'caption': context.__model__.__name__ + 's',
            'grid': grid, 'page': page}
