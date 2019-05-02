HOST = '0.0.0.0'
PORT = 8080
DEBUG = False
POLICIES_DIR = '/etc/greenwave/'
DIST_GIT_BASE_URL = 'https://src.fedoraproject.org'
DIST_GIT_URL_TEMPLATE = '{DIST_GIT_BASE_URL}/{pkg_namespace}/{pkg_name}/raw/{rev}/f/gating.yaml'
KOJI_BASE_URL = 'https://koji.fedoraproject.org/kojihub'

SECRET_KEY = 'this-is-only-for-integration-testing'
WAIVERDB_API_URL = 'http://waiverdb:8080/api/v1.0'
RESULTSDB_API_URL = 'http://resultsdb/resultsdb/api/v2.0'
CORS_URL = 'https://bodhi'
CACHE = {
    "backend": "dogpile.cache.memory_pickle",
}
