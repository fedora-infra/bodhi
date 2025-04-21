SECRET_KEY = 'this-is-only-for-integration-testing'
SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg2://resultsdb@db/resultsdb'
HOST = '0.0.0.0'
PORT = 5001
FILE_LOGGING = False
LOGFILE = '/var/log/resultsdb/resultsdb.log'
SYSLOG_LOGGING = False
STREAM_LOGGING = True

MESSAGE_BUS_PUBLISH = False
MESSAGE_BUS_PUBLISH_TASKOTRON = False
# TODO: integration testing of published fedmsgs?
# MESSAGE_BUS_PUBLISH = True
# MESSAGE_BUS_PUBLISH_TASKOTRON = True

MESSAGE_BUS_PLUGIN = 'fedmsg'
MESSAGE_BUS_KWARGS = {'modname': 'resultsdb'}
