#!/usr/bin/env python3

import json
import sqlite3
import time


CLIENT_STATIC_DB = "/var/lib/ipsilon/root/openidc.static.sqlite"
CLIENT_DB = "/var/lib/ipsilon/root/openidc.sqlite"
USERPREFS_DB = "/var/lib/ipsilon/root/userprefs.sqlite"
SCOPES = [
    "openid", "email", "profile",
    "https://id.fedoraproject.org/scope/groups",
    "https://id.fedoraproject.org/scope/agreements"
]

CLIENTS = [
    {
        "client_id": "bodhi-client",
        "client_secret": "",
        "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
        "application_type": "native",
        "response_types": ["code"],
        "grant_types": ["authorization_code"],
        "client_id_issued_at": int(time.time()),
        "ipsilon_internal": {"trusted": True, "client_id": "bodhi-client", "type": "static"},
        "client_secret_expires_at": 0,
        "token_endpoint_auth_method": "none",
    },
    {
        "client_id": "integration-tests",
        "client_secret": "integration-tests",
        "redirect_uris": ["http://bodhi.ci:8080/oidc/authorize"],
        "application_type": "web",
        "response_types": ["code"],
        "grant_types": ["authorization_code"],
        "client_id_issued_at": int(time.time()),
        "ipsilon_internal": {"trusted": True, "client_id": "integration-tests", "type": "static"},
        "client_secret_expires_at": 0,
        "token_endpoint_auth_method": "client_secret_post",
    },
]

TOKENS = [
    {
        "type": "Bearer",
        "security_check": "code",
        "client_id": "bodhi-client",
        "username": "guest",
        "scope": json.dumps(SCOPES),
        "expires_at": 1643980480,
        "issued_at": 1643980480 - 3600,
        "refreshable": 1,
        "refresh_security_check": "refresh",
        "userinfocode": "guest",
    }
]

USERINFO = {
    "guest": {
        "name": "Guest",
        "nickname": "guest",
        "email": "guest@example.com",
        "groups": ["packager", "fedora-contributors", "proventesters", "provenpackager"],
        "sub": "guest",
    }
}


conn = sqlite3.connect(CLIENT_STATIC_DB)
with conn:
    # Register the bodhi apps (client & server)
    for client in CLIENTS:
        primary_key = client["client_id"]
        for name, value in client.items():
            conn.execute(
                "INSERT INTO client(name, option, value) VALUES (?, ?, ?)",
                (client["client_id"], name, json.dumps(value))
            )

conn = sqlite3.connect(CLIENT_DB)
with conn:
    # Add the tokens
    for token in TOKENS:
        for name, value in token.items():
            conn.execute(
                "INSERT INTO token(uuid, name, value) VALUES (?, ?, ?)",
                ("access", name, value)
            )

    # Add the userinfo
    for userinfocode, data in USERINFO.items():
        for name, value in data.items():
            conn.execute(
                "INSERT INTO userinfo VALUES (?, ?, ?)",
                (userinfocode, name, json.dumps(value))
            )

# Add the consent for the guest user
conn = sqlite3.connect(USERPREFS_DB)
with conn:
    conn.execute(
        "INSERT INTO user_consent(name, option, value) VALUES (?, ?, ?)",
        (
            "guest",
            "openidc-bodhi-client",
            json.dumps({
                "claims": ["email", "groups", "name", "nickname", "preferred_username"],
                "scopes": SCOPES,
            })
        )
    )
