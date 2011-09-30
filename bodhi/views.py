from webhelpers.html.grid import Grid
from webhelpers.paginate import Page, PageURL_WebOb

from bodhi.models import DBSession

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
    return {'caption': context.__model__.__name__ + 's',
            'grid': grid, 'page': page}


## 404

def notfound_view(context, request):
    request.response_status = 404
    return dict()

## Widgets

def view_widget(context, request):
    import tw2.core
    context.fetch_data(request)
    mw = tw2.core.core.request_local()['middleware']
    mw.controllers.register(context, 'update_submit')
    return {'widget':context}
