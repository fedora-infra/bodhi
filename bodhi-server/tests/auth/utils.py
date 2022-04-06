"""Utility functions for the authentication unit tests."""

from authlib import __version__ as authlib_version
from packaging.version import parse as parse_version


def set_session_data(session, state, key, value, app_name="dev"):
    """Set the session data with any Authlib version."""
    if parse_version(authlib_version) < parse_version("1.0.0"):
        session[f"_{app_name}_authlib_{key}_"] = value
    else:
        session[f'_state_{app_name}_{state}'] = {"data": {key: value}}


def get_session_data(session, state, key, app_name="dev"):
    """Get the session data with any Authlib version."""
    if parse_version(authlib_version) < parse_version("1.0.0"):
        return session[f"_{app_name}_authlib_{key}_"]
    else:
        return session[f'_state_{app_name}_{state}']["data"][key]
