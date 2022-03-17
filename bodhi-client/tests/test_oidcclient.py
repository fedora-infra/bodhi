import threading
import time

from authlib.integrations.base_client.errors import OAuthError
from click import ClickException
import pytest
import requests

from bodhi.client.oidcclient import JSONStorage, OIDCClient, OIDCClientError

from .utils import build_response


@pytest.fixture
def storage(mocker):
    obj = mocker.Mock(name="storage")
    obj.load.return_value = {}
    return obj


@pytest.fixture
def client(mocker, storage):
    requests_mock = mocker.patch("bodhi.client.oidcclient.requests")
    response = mocker.Mock()
    response.json.return_value = {
        "token_endpoint": "http://id.example.com/token",
        "authorization_endpoint": "http://id.example.com/auth",
        "response_modes_supported": ["query", "none"]
    }
    requests_mock.get.return_value = response
    client = OIDCClient("client_id", "scope", "http://id.example.com", storage)
    mocker.stopall()
    return client


def test_oidcclient(mocker, storage):
    metadata = {"token_endpoint": "http://id.example.com/token"}
    requests_mock = mocker.patch("bodhi.client.oidcclient.requests")
    response = mocker.Mock()
    response.json.return_value = metadata
    requests_mock.get.return_value = response
    client = OIDCClient("client_id", "scope", "http://id.example.com", storage)
    assert client.client_id == "client_id"
    assert client.scope == "scope"
    assert client.storage == storage
    requests_mock.get.assert_called_with("http://id.example.com/.well-known/openid-configuration")
    assert client.metadata == metadata


def test_oidcclient_use_oob(mocker, storage):
    requests_mock = mocker.patch("bodhi.client.oidcclient.requests")
    response = mocker.Mock()
    requests_mock.get.return_value = response

    # Test unsupported
    response.json.return_value = {
        "token_endpoint": "http://id.example.com/token",
        "response_modes_supported": ["query", "none"]
    }
    client = OIDCClient("client_id", "scope", "http://id.example.com", storage)
    assert client._use_oob is False
    assert client.redirect_uri == "http://localhost:45678/auth"
    # Test supported
    response.json.return_value = {
        "token_endpoint": "http://id.example.com/token",
        "response_modes_supported": ["query", "none", "oob"]
    }
    client = OIDCClient("client_id", "scope", "http://id.example.com", storage)
    assert client._use_oob is True
    assert client.redirect_uri == "urn:ietf:wg:oauth:2.0:oob"


def test_oidcclient_metadata_error(mocker, storage):
    requests_mock = mocker.patch("bodhi.client.oidcclient.requests")
    requests_mock.get.return_value = build_response(404, "/metadata", "not found")
    with pytest.raises(OIDCClientError) as exc:
        OIDCClient("client_id", "scope", "http://id.example.com", storage)
    requests_mock.get.assert_called_with("http://id.example.com/.well-known/openid-configuration")
    assert str(exc.value) == "not found"


def test_oidcclient_login(mocker, client):
    oauth2client = mocker.Mock()
    client.client = oauth2client
    mocker.patch("bodhi.client.oidcclient.click.prompt", return_value="result-code")
    # Enable OOB
    client.metadata = {
        "token_endpoint": "http://id.example.com/token",
        "authorization_endpoint": "http://id.example.com/auth",
        "response_modes_supported": ["oob"]
    }
    oauth2client.create_authorization_url.return_value = ("auth-url", "state")
    oauth2client.fetch_token.return_value = "result-token"
    client.login()
    oauth2client.create_authorization_url.assert_called_with("http://id.example.com/auth")
    oauth2client.fetch_token.assert_called_with(
        'http://id.example.com/token',
        authorization_response="?result-code",
        redirect_uri='urn:ietf:wg:oauth:2.0:oob',
    )
    assert client.tokens == "result-token"


def test_oidcclient_login_no_oob(mocker, client):
    oauth2client = mocker.Mock()
    client.client = oauth2client
    # No OOB
    client.metadata = {
        "token_endpoint": "http://id.example.com/token",
        "authorization_endpoint": "http://id.example.com/auth",
        "response_modes_supported": []
    }
    oauth2client.create_authorization_url.return_value = ("auth-url", "state")
    oauth2client.fetch_token.return_value = "result-token"
    login_thread = threading.Thread(target=client.login)
    login_thread.start()
    # Give the embedded HTTP server some time to start up.
    time.sleep(1)
    response = requests.get(client.redirect_uri, params={"code": "CODE"})
    login_thread.join()
    assert response.ok is True
    assert "Authentication successful!" in response.text
    assert "You can now close this browser window" in response.text

    oauth2client.fetch_token.assert_called_once_with(
        'http://id.example.com/token',
        authorization_response="/auth?code=CODE",
        redirect_uri=client.redirect_uri,
    )
    assert client.tokens == "result-token"


def test_oidcclient_login_no_oob_interrupted(mocker, client):
    oauth2client = mocker.Mock()
    client.client = oauth2client
    # No OOB
    client.metadata = {
        "token_endpoint": "http://id.example.com/token",
        "authorization_endpoint": "http://id.example.com/auth",
        "response_modes_supported": []
    }
    oauth2client.create_authorization_url.return_value = ("auth-url", "state")
    mocker.patch.object(threading.Thread, "start")
    mocker.patch.object(threading.Thread, "join", side_effect=[KeyboardInterrupt, None])
    with pytest.raises(ClickException) as exc:
        client.login()
    assert str(exc.value) == "Cancelled."


def test_oidcclient_login_no_oob_failure(mocker, client):
    oauth2client = mocker.Mock()
    client.client = oauth2client
    # No OOB
    client.metadata = {
        "token_endpoint": "http://id.example.com/token",
        "authorization_endpoint": "http://id.example.com/auth",
        "response_modes_supported": []
    }
    oauth2client.create_authorization_url.return_value = ("auth-url", "state")
    oauth2client.fetch_token.side_effect = ValueError("not good")
    login_thread = threading.Thread(target=client.login)
    login_thread.start()
    # Give the embedded HTTP server some time to start up.
    time.sleep(1)
    response = requests.get(client.redirect_uri, params={"code": "CODE"})
    login_thread.join()
    assert response.ok is False
    assert "not good" in response.text


def test_oidcclient_login_interrupted(mocker, client):
    oauth2client = mocker.Mock()
    client.client = oauth2client
    mocker.patch("bodhi.client.oidcclient.click.prompt", side_effect=KeyboardInterrupt)
    # Enable OOB
    client.metadata = {
        "token_endpoint": "http://id.example.com/token",
        "authorization_endpoint": "http://id.example.com/auth",
        "response_modes_supported": ["oob"]
    }
    oauth2client.create_authorization_url.return_value = ("auth-url", "state")
    with pytest.raises(ClickException) as exc:
        client.login()
    oauth2client.fetch_token.assert_not_called()
    assert str(exc.value) == "Cancelled."


def test_oidcclient_login_retry(mocker, client):
    oauth2client = mocker.Mock()
    client.client = oauth2client
    client._tokens = None
    client.storage.load.side_effect = lambda k, d: d
    prompt = mocker.patch("bodhi.client.oidcclient.click.prompt")
    prompt.return_value = "result-code"
    secho = mocker.patch("bodhi.client.oidcclient.click.secho")
    # Enable OOB
    client.metadata = {
        "token_endpoint": "http://id.example.com/token",
        "authorization_endpoint": "http://id.example.com/auth",
        "response_modes_supported": ["oob"]
    }
    oauth2client.create_authorization_url.return_value = ("auth-url", "state")
    oauth2client.fetch_token.side_effect = [
        OAuthError("nope", "wrong"),
        OAuthError("nope", "wrong again"),
        "result-token",
    ]

    client.login()

    assert prompt.call_count == 3
    assert oauth2client.fetch_token.call_count == 3
    assert client.tokens == "result-token"
    assert secho.call_args_list == [
        mocker.call("Authenticating... Please open your browser to:", fg="yellow"),
        mocker.call("Login failed!: nope: wrong. Please try again.", fg="red"),
        mocker.call("Login failed!: nope: wrong again. Please try again.", fg="red"),
        mocker.call("Login successful!", fg="green"),
    ]


def test_oidcclient_reuse_token(mocker, client, storage):
    # Reset the tokens cache
    client._tokens = None
    client.storage.load.return_value = {"http://id.example.com": {"foo": "bar"}}
    assert client.tokens == {"foo": "bar"}
    login = mocker.patch.object(client, "login")
    client.ensure_auth()
    login.assert_not_called


def test_oidcclient_username(mocker, client):
    oauth2client = mocker.Mock()
    client.client = oauth2client
    client._tokens = {"access_token": "TOKEN"}
    client.metadata = {
        "userinfo_endpoint": "http://id.example.com/user",
    }
    response = mocker.Mock()
    response.json.return_value = {"nickname": "NICKNAME"}
    oauth2client.get.return_value = response
    assert client.username == "NICKNAME"
    oauth2client.get.assert_called_with("http://id.example.com/user")


def test_oidcclient_request(mocker, client):
    client._tokens = {"access_token": "TOKEN"}
    client.client.token_auth.set_token({"access_token": "TOKEN"})
    request = mocker.patch.object(client.client, "request")
    client.request("GET", "http://id.example.com")
    request.assert_called_with("GET", "http://id.example.com")


def test_oidcclient_request_connection_error(mocker, client):
    client._tokens = {"access_token": "TOKEN"}
    client.client.token_auth.set_token({"access_token": "TOKEN"})
    request = mocker.patch.object(client.client, "request")
    request.side_effect = requests.exceptions.ConnectionError("failed!")
    with pytest.raises(OIDCClientError) as exc:
        client.request("GET", "http://id.example.com")
    assert str(exc.value) == "failed!"


def test_oidcclient_request_auth_error(mocker, client):
    client._tokens = {"access_token": "TOKEN"}
    client.client.token_auth.set_token({"access_token": "TOKEN"})
    request = mocker.patch.object(client.client, "request")
    request.side_effect = [
        OAuthError("failed!"),
        "OK this time",
    ]
    login = mocker.patch.object(client, "login")

    result = client.request("GET", "http://id.example.com")

    assert result == "OK this time"
    assert request.call_count == 2
    login.assert_called_with()
    assert client.tokens == {}


def test_oidcclient_clear_auth(mocker, client):
    client._tokens = {"access_token": "TOKEN"}
    client._username == "NICKNAME"
    client.client.token_auth.set_token({"access_token": "TOKEN"})
    client.client.cookies.set("foo", "bar")
    login = mocker.patch.object(client, "login")
    client.metadata = {
        "userinfo_endpoint": "http://id.example.com/user",
    }
    request = mocker.patch.object(client.client, "request")

    client.clear_auth()

    assert client.tokens == {}
    assert client.client.token_auth.token == {}
    print(client.client.cookies.list_domains())
    assert not client.has_cookie("foo")
    # Now make sure we login again if asked to.
    client.ensure_auth()
    login.assert_called
    assert client.username != "NICKNAME"
    request.assert_called_with("GET", "http://id.example.com/user", allow_redirects=True)


def test_oidcclient_has_cookie(client):
    client.client.cookies.clear()
    assert client.has_cookie("foo") is False
    client.client.cookies.set("foo", "bar", domain="localhost.local")
    assert client.has_cookie("foo") is True
    # has_cookie() should add ".local" when not fully qualified
    assert client.has_cookie("foo", domain="localhost") is True
    assert client.has_cookie("foo", domain="example.com") is False


def test_oidcclient_update_token(client):
    client._update_token({"foo": "bar"})
    assert client.tokens == {"foo": "bar"}


def test_storage(tmpdir):
    storage = JSONStorage(tmpdir.join("storage.json"))
    storage.save("tokens", {"foo": "bar"})
    assert storage.load("tokens") == {"foo": "bar"}


def test_storage_make_directory(tmpdir):
    storage = JSONStorage(tmpdir.join("subdir", "storage.json"))
    storage.save("tokens", {"foo": "bar"})
    assert storage.load("tokens") == {"foo": "bar"}
