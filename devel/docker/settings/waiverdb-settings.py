DATABASE_URI = 'postgresql+psycopg2://waiverdb@wdb:5432/waiverdb'
RESULTSDB_API_URL = 'https://resultsdb.fedoraproject.org/api/v2.0'
SECRET_KEY = 'this-is-only-for-development'
CORS_URL = '*'

# MESSAGE_BUS_PUBLISH = True
MESSAGE_BUS_PUBLISH = False

AUTH_METHOD = 'dummy'
SUPERUSERS = ['bodhi_user']
PORT = 6544
