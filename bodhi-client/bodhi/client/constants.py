"""Constants for the Bodhi Client."""

BASE_URL = "https://bodhi.fedoraproject.org/"
IDP = "https://id.fedoraproject.org/openidc"
CLIENT_ID = "bodhi-client"
STG_BASE_URL = "https://bodhi.stg.fedoraproject.org/"
STG_IDP = "https://id.stg.fedoraproject.org/openidc"
STG_CLIENT_ID = "bodhi-client"
SCOPE = " ".join([
    "openid",
    "email",
    "profile",
    "https://id.fedoraproject.org/scope/groups",
    "https://id.fedoraproject.org/scope/agreements",
])
UPDATE_TYPES = ['security', 'bugfix', 'enhancement', 'newpackage']
REQUEST_TYPES = ['testing', 'stable', 'unpush']
SUGGEST_TYPES = ['unspecified', 'reboot', 'logout']
