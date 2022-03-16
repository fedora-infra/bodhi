"""A generic OIDC client that can use OOB or not."""

from functools import partial
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import threading

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.requests_client import OAuth2Session
from authlib.oidc.discovery.well_known import get_well_known_url
import click
import requests


PORT = 45678  # Hopefully nothing else uses this on the host...

RESULT_SUCCESS = """
<html>
    <head>
        <title>Authentication successful!</title>
        <style>
            p {
                margin-top: 2em;
                font-size: 130%;
                text-align: center;
            }
        </style>
    </head>
    <body>
        <p>
            <strong>Authentication successful!</strong>
            You can now close this browser window and go back to bodhi's command-line.
        </p>
    </body>
</html>
"""


class OIDCClientError(Exception):
    """Raised when there's an error in the OIDCClient class."""


class OIDCClient:
    """A client for OpenID Connect authentication."""

    def __init__(
        self, client_id, scope, id_provider, storage
    ):
        """Initialize OIDCClient.

        Args:
            client_id (str): The OIDC client ID.
            scope (str): The OIDC scopes that will be asked.
            id_provider (str): The URL to the OIDC provider.
            storage (JSONStorage): An instance of JSONStorage to store the tickets.
        """
        self.client_id = client_id
        self.scope = scope
        self.id_provider = id_provider
        self.storage = storage
        self._tokens = None
        self._username = None
        self.metadata = {}
        self._build_client(client_id, scope, id_provider)

    def _get_provider_metadata(self, id_provider):
        metadata_endpoint = get_well_known_url(id_provider, external=True)
        response = requests.get(metadata_endpoint)
        if not response.ok:
            raise OIDCClientError(response.text)
        self.metadata = response.json()

    def _build_client(self, client_id, scope, id_provider):
        self._get_provider_metadata(id_provider)
        self.client = OAuth2Session(
            client_id,
            scope=scope,
            token_endpoint_auth_method="none",
            redirect_uri=self.redirect_uri,
            update_token=self._update_token,
            token_endpoint=self.metadata["token_endpoint"],
            token=self.tokens,
        )

    @property
    def _use_oob(self):
        return "oob" in self.metadata.get("response_modes_supported", [])

    @property
    def redirect_uri(self):
        """Return the OIDC redirect URI.

        The value will depend on the server's ability to do OOB authentication.

        Returns:
            str: The OIDC redirect URI.
        """
        if self._use_oob:
            return "urn:ietf:wg:oauth:2.0:oob"
        else:
            return f"http://localhost:{PORT}/auth"

    @property
    def username(self):
        """Return the authenticated user name.

        This will trigger authentication.

        Returns:
            str or None: The authenticated username or ``None`` if we couldn't authenticate.
        """
        if self._username is None:
            self.ensure_auth()
            response = self.client.get(self.metadata["userinfo_endpoint"])
            if response.ok:
                self._username = response.json()["nickname"]
        return self._username

    def login(self):
        """Login to the OIDC provider.

        If authentication fails, it will be retried.

        Raises:
            click.ClickException: When authentication was cancelled.
        """
        authorization_endpoint = self.metadata["authorization_endpoint"]
        uri, state_ = self.client.create_authorization_url(authorization_endpoint)
        click.secho("Authenticating... Please open your browser to:", fg="yellow")
        click.echo(uri)
        if self._use_oob:
            while True:
                try:
                    value = click.prompt(
                        click.style(
                            "Paste here the code that you got after logging in", fg="yellow"
                        )
                    )
                except KeyboardInterrupt:
                    raise click.ClickException("Cancelled.")
                try:
                    self.auth_callback(f"?{value}")
                except OAuthError as e:
                    click.secho(f"Login failed!: {e}. Please try again.", fg="red")
                if self.tokens:
                    break
        else:
            self._run_http_server()
        click.secho("Login successful!", fg="green")

    def _run_http_server(self):
        httpd = HTTPServer(
            ("localhost", PORT), partial(RequestHandler, callback=self.auth_callback)
        )
        server_thread = threading.Thread(target=httpd.serve_forever)
        # Exit the server thread when the main thread terminates
        server_thread.daemon = True
        server_thread.start()
        try:
            server_thread.join()
        except KeyboardInterrupt:
            stop_thread = threading.Thread(target=httpd.shutdown, daemon=True)
            stop_thread.start()
            stop_thread.join()
            raise click.ClickException("Cancelled.")
        finally:
            httpd.server_close()

    def auth_callback(self, response):
        """Handle OIDC callback (post-login).

        Args:
            response (str): The authorization response that the OIDC provider sent.
        """
        self.tokens = self.client.fetch_token(
            self.metadata["token_endpoint"],
            authorization_response=response,
            redirect_uri=self.redirect_uri,
        )

    def ensure_auth(self):
        """Make sure the client is authenticated."""
        if not self.tokens:
            self.login()

    @property
    def tokens(self):
        """Return the authentication tokens, or None if we don't have any yet.

        Returns:
            dict: The authentication tokens.
        """
        if self._tokens is None:
            self._tokens = self.storage.load("tokens", {}).get(self.id_provider)
        return self._tokens

    @tokens.setter
    def tokens(self, value):
        self._tokens = value
        stored_tokens = self.storage.load("tokens", {})
        stored_tokens[self.id_provider] = value
        self.storage.save("tokens", stored_tokens)

    def _update_token(self, token, refresh_token=None, access_token=None):
        self.tokens = token

    def request(self, *args, **kwargs):
        """Make an authenticated request.

        The request will have a Bearer authentication token using the OIDC access_token.

        Raises:
            OIDCClientError: When the connection fails

        Returns:
            Response: The request's response.
        """
        self.ensure_auth()
        try:
            return self.client.request(*args, **kwargs)
        except requests.exceptions.ConnectionError as e:
            raise OIDCClientError(str(e))
        except OAuthError:
            # Auth failed, clear it and retry
            self.clear_auth()
            return self.request(*args, **kwargs)

    def has_cookie(self, name, domain=None):
        """Return whether the OIDC client has a cookie of the provided name.

        Args:
            name (str): The name of the cookie.
            domain (str or None): The domain of the cookie. Defaults to None for any domain.

        Returns:
            bool: True if the HTTP client has this cookie, False otherwise.
        """
        if domain is not None and "." not in domain:
            domain += ".local"
        return self.client.cookies.get(name, domain=domain) is not None

    def clear_auth(self):
        """Clear the authentication tokens and cache."""
        self.tokens = {}
        self._username = None
        self.client.token_auth.set_token({})
        self.client.cookies.clear()


class RequestHandler(BaseHTTPRequestHandler):
    """A request handler for the embedded HTTP server."""

    def __init__(self, *args, **kwargs):
        """Initialize the request handler."""
        self.callback = kwargs.pop("callback")
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET requests."""
        try:
            self.callback(self.path)
        except Exception as e:
            click.echo(e, err=True)
            self.send_error(500, str(e))
        else:
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(RESULT_SUCCESS.encode("utf-8"))
        threading.Thread(target=self.server.shutdown, daemon=True).start()


class JSONStorage:
    """Store dictionaries as JSON in a regular file."""

    def __init__(self, path):
        """Initialize the JSONStorage object.

        Args:
            path (str): The path to the JSON file.
        """
        self.path = path

    def load_all(self):
        """Load all the data from the file.

        Returns:
            dict: The stored data.
        """
        if not os.path.exists(self.path):
            return {}
        with open(self.path) as f:
            return json.load(f)

    def load(self, key, default=None):
        """Load a specific key from the storage.

        Args:
            key (str): The key to load
            default (any, optional): What to return if the key is not found in the storage.
                Defaults to None.

        Returns:
            any: The stored value for the specified key.
        """
        return self.load_all().get(key, default)

    def save(self, key, value):
        """Save a value in the store.

        Args:
            key (str): The key to store the value as.
            value (any): The value to store. It must be JSON-serializable.
        """
        data = self.load_all()
        data[key] = value
        parent_dir = os.path.dirname(self.path)
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir)
        with open(self.path, "w") as f:
            json.dump(data, f)
