from pyramid.security import effective_principals
from cornice import Service

from bodhi import log
from bodhi.security import admin_only_acl

admin_service = Service(name='admin', path='/admin/',
                        description='Administrator view',
                        acl=admin_only_acl)

@admin_service.get(permission='admin')
def admin(request):
    user = request.user
    log.info('%s logged into admin panel' % user.name)
    principals = effective_principals(request)
    return {'user': user.name, 'principals': principals}
