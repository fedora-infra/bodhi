"""Constants for the Bodhi Client."""

BASE_URL = "https://bodhi.fedoraproject.org/"
IDP = "https://id.fedoraproject.org/openidc"
CLIENT_ID = "D-9bae161a-a8e3-44ac-ad57-09079d980625"
STG_BASE_URL = "https://bodhi.stg.fedoraproject.org/"
STG_IDP = "https://id.stg.fedoraproject.org/openidc"
STG_CLIENT_ID = "D-9bae161a-a8e3-44ac-ad57-09079d980625"
SCOPE = " ".join([
    "openid",
    "email",
    "profile",
    "https://id.fedoraproject.org/scope/groups",
    "https://id.fedoraproject.org/scope/agreements",
])
