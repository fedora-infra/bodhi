DATABASE_URI = 'postgresql+psycopg2://waiverdb@db:5432/waiverdb'
SECRET_KEY = 'this-is-only-for-integration-testing'
RESULTSDB_API_URL = 'https://resultsdb:8080/api/v2.0'
CORS_URL = 'https://bodhi'

# TODO: integration testing of published fedmsgs?
# MESSAGE_BUS_PUBLISH = True
MESSAGE_BUS_PUBLISH = False

AUTH_METHOD = 'dummy'
SUPERUSERS = ['bodhi@service']
PORT = 8080
