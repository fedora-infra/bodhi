"""Tween to hook prometheus metric collection into pyramid."""


from time import time

from prometheus_client import Histogram, Gauge
from pyramid.interfaces import IRoutesMapper


def get_pattern(request):
    """
    Extract the pattern from request.

    For example `/updates/FEDORA-2019-0c2e93b669` to `/updates/{id}`
    """
    path_info_pattern = ''
    if request.matched_route is None:
        routes_mapper = request.registry.queryUtility(IRoutesMapper)
        if routes_mapper:
            info = routes_mapper(request)
            if info and info['route']:
                path_info_pattern = info['route'].pattern
    else:
        path_info_pattern = request.matched_route.pattern
    return path_info_pattern


pyramid_request_ingress = Gauge(
    'pyramid_request_ingress',
    'Number of requests currrently processed',
    labelnames=['method', 'path_info_pattern'],)


pyramid_request = Histogram(
    'pyramid_request',
    'HTTP Requests',
    labelnames=['method', 'status', 'path_info_pattern']
)


def histo_tween_factory(handler, registry):
    """
    Create a tween to monitor number of requests at a given time.

    Collects metrics on individual requests.
    """
    def tween(request):
        gauge_labels = {
            'method': request.method,
            'path_info_pattern': get_pattern(request),
        }
        pyramid_request_ingress.labels(**gauge_labels).inc()

        start = time()
        status = '500'
        try:
            response = handler(request)
            status = str(response.status_int)
            return response
        finally:
            duration = time() - start
            pyramid_request.labels(
                method=request.method,
                path_info_pattern=get_pattern(request),
                status=status,
            ).observe(duration)
            pyramid_request_ingress.labels(**gauge_labels).dec()
    return tween
