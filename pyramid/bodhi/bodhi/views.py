from webhelpers.html.grid import Grid
from webhelpers.paginate import Page, PageURL_WebOb

from bodhi.models import DBSession

## JSON views

def view_model_instance_json(context, request):
    return {'context': context.__json__()}

def view_model_json(context, request):
    session = DBSession()
    # TODO: pagination
    entries = session.query(context.__model__).all()
    return {'entries': [entry.__json__() for entry in entries]}

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
    # FIXME: entries[0] triggers another query
    grid = Grid([entry.__json__() for entry in page], entries[0].grid_columns)
    return {'caption': context.__model__.__name__ + 's',
            'grid': grid, 'page': page}
