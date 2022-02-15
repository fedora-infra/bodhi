"""Some utilities for bodhi-server's unit tests."""

from unittest import mock, TestCase
import time

import requests


_dummy = TestCase()
assert_multiline_equal = _dummy.assertMultiLineEqual


def mock_send_value(body, status_code=200):
    """Mock an HTTP response.

    Args:
        body (str or dict): The content of the response.
        status_code (int, optional): The HTTP status code. Defaults to 200.

    Returns:
        mock.Mock: A ``requests.Response``-compatible mock object.
    """
    resp = mock.MagicMock(spec=requests.Response)
    resp.cookies = []
    if isinstance(body, dict):
        resp.json = lambda: body
    else:
        resp.text = body
    resp.status_code = status_code
    return resp


def get_bearer_token():
    """Get a Bearer token that expires in one hour."""
    return {
        'token_type': 'Bearer',
        'access_token': 'a',
        'refresh_token': 'b',
        'expires_in': '3600',
        'expires_at': int(time.time()) + 3600,
    }
