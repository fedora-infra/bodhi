"""Constants that do not need to be configurable."""

SCOPES = " ".join(  #noqa: FLY002
    [
        "openid",
        "email",
        "profile",
        "https://id.fedoraproject.org/scope/groups",
        "https://id.fedoraproject.org/scope/agreements",
    ]
)
