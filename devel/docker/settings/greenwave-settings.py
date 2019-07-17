HOST = '0.0.0.0'
PORT = 6545
DEBUG = False
POLICIES_DIR = '/etc/greenwave/policies/'
DIST_GIT_BASE_URL = 'https://src.fedoraproject.org'
DIST_GIT_URL_TEMPLATE = '{DIST_GIT_BASE_URL}/{pkg_namespace}/{pkg_name}/raw/{rev}/f/gating.yaml'
KOJI_BASE_URL = 'https://koji.fedoraproject.org/kojihub'

SECRET_KEY = 'this-is-only-for-development'
WAIVERDB_API_URL = 'http://waiverdb:6544/api/v1.0'
RESULTSDB_API_URL = 'https://taskotron.fedoraproject.org/resultsdb_api/api/v2.0'
CORS_URL = '*'
CACHE = {
    "backend": "dogpile.cache.memory_pickle",
}
