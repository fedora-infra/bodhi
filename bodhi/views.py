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
    context.fetch_data(request)
    mw = tw2.core.core.request_local()['middleware']
    mw.controllers.register(context, 'update_submit')
    return {'widget':context}


def save(request):
    print request.params

    # Validate the CSRF token
    #token = request.session.get_csrf_token()
    #if token != request.POST['csrf_token']:
    #    raise ValueError('CSRF token did not match')

    # Validate parameters
    try:
        validated = NewUpdateForm.validate(request.POST)
    except tw2.core.ValidationError, ve:
        # TODO
        print ve
        raise

    from pprint import pprint
    pprint(validated)

    ## Sanity checks
    # Check for conflicting builds
    # Make sure update doesn't exist
    # Make sure submitter has commit access
    # Editing magic
    # Make sure builds are tagged properly
    # Create model instances
    # Obsolete any older updates, inherit data
    # Bugzilla interactions
    # Security checks
    # Look for unit tests
    # Send out email notifications
    # Set request, w/ critpath checks


@cache_region('long_term', 'package_list')
def get_all_packages():
    """ Get a list of all packages in Koji """
    log.debug('Fetching list of all packages...')
    koji = buildsys.get_session()
    return [pkg['package_name'] for pkg in koji.listPackages()]
