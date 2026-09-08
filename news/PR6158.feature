The WSGI application and Celery tasks now opt into the process's hard file limit. Previously, both
used the default soft limit, which for most platforms is 1024.
