# Copyright © 2018 Red Hat, Inc.
#
# This file is part of Bodhi.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
"""
Copy containers between registries.

This is a very limited version of the skopeo tool, but with support
for manifests lists and OCI image indexes.
https://github.com/containers/image/pull/400 will make this
unnecessary.

The only subcommand that is supported is 'copy', and the only supported image references
are Docker registry references of the form 'docker://docker-reference'.

No global options are supported, and only selected options to 'copy' are supported (see
--help for details.)

Some other things that aren't implemented (but could be added if necessary):
 - Handling of www-authenticate responses, necessary to log in to docker.io
 - Special handling of 'docker.io' as 'registry-1.docker.io'
 - Reading ~/.docker/config.json or $XDG_RUNTIME_DIR/containers/auth.json
 - Handling foreign layers
"""

from urllib.parse import urlparse, urlunparse
import json
import logging
import os
import shutil
import tempfile

import click
import requests
from requests.exceptions import SSLError, ConnectionError


@click.group()
def main():
    """Simplified Skopeo work-alike with manifest list support."""
    pass  # pragma: no cover


logger = logging.getLogger('skopeo-lite')
logging.basicConfig(level=logging.INFO)


MEDIA_TYPE_MANIFEST_V2 = 'application/vnd.docker.distribution.manifest.v2+json'
MEDIA_TYPE_LIST_V2 = 'application/vnd.docker.distribution.manifest.list.v2+json'
MEDIA_TYPE_OCI = 'application/vnd.oci.image.manifest.v1+json'
MEDIA_TYPE_OCI_INDEX = 'application/vnd.oci.image.index.v1+json'


class RegistrySpec(object):
    """Information about a docker registry/repository/tag as specified on the command line."""

    def __init__(self, registry, repo, tag, creds, tls_verify, cert_dir):
        """
        Initialize the registry spec.

        Args:
           registry (str): The hostname.
           repo (str): The repository name within the registry.
           tag (str): The tag within the repository.
           creds (str): user:password (may be None).
           tls_verify (bool): If True, HTTPS with a verified certificate is required.
           cert_dir (str): A path to directory holding client certificates, or None.
        """
        self.registry = registry
        self.repo = repo
        self.tag = tag
        self.creds = creds
        self.cert_dir = cert_dir
        self.tls_verify = tls_verify

    def get_session(self):
        """Create a RegistrySession object for the spec."""
        return RegistrySession(self.registry, insecure=not self.tls_verify,
                               creds=self.creds, cert_dir=self.cert_dir)

    def get_endpoint(self):
        """Create a RegistryEndpoint object for the spec."""
        return RegistryEndpoint(self)


def parse_spec(spec, creds, tls_verify, cert_dir):
    """
    Parse a string into a RegistrySpec, adding extra information.

    Args:
       spec (str): docker://<hostname>/<repo>[:tag] - latest will be used
           if tag is omitted.
       creds (str): user:password (may be None).
       tls_verify (bool): If True https with a verified certificate is required
       cert_dir (str): A path to directory holding client certificates, or None.
    Returns:
       RegistrySpec: The resulting registry spec.
    Raises:
       click.BadArgumentUsage: If the string cannot be parsed
    """
    if spec.startswith('docker:'):
        if not spec.startswith('docker://'):
            raise click.BadArgumentUsage(
                "Registry specification should be docker://REGISTRY/PATH[:TAG]")

        parts = spec[len('docker://'):].split('/', 1)
        if len(parts) == 1:
            raise click.BadArgumentUsage(
                "Registry specification should be docker://REGISTRY/PATH[:TAG]")

        registry, path = parts
        parts = path.split(':', 1)
        if len(parts) == 1:
            repo, tag = parts[0], 'latest'
        else:
            repo, tag = parts

        return RegistrySpec(registry, repo, tag, creds, tls_verify, cert_dir)
    else:
        raise click.BadArgumentUsage("Unknown source/destination: {}".format(spec))


class RegistrySession(object):
    """Wrapper around requests.Session adding docker-specific behavior."""

    def __init__(self, registry, insecure=False, creds=None, cert_dir=None):
        """
        Initialize the RegistrySession.

        Args:
            registry (str): The hostname of the registry.
            insecure (bool): If True don't verify TLS certificates and fallback to HTTP.
            creds (str): user:password (may be None).
            cert_dir (str): A path to directory holding client certificates, or None.
        """
        self.registry = registry
        self._resolved = None
        self.insecure = insecure

        self.cert = self._find_cert(cert_dir)

        self.auth = None
        if creds is not None:
            username, password = creds.split(':', 1)
            self.auth = requests.auth.HTTPBasicAuth(username, password)

        self._fallback = None
        self._base = 'https://{}'.format(self.registry)
        if insecure:
            # In the insecure case, if the registry is just a hostname:port, we
            # don't know whether to talk HTTPS or HTTP to it, so we try first
            # with https then fallback
            self._fallback = 'http://{}'.format(self.registry)

        self.session = requests.Session()

    def _find_cert_dir(self):
        """
        Return a path to a directory containing TLS client certificates to use for authentication.

        Returns:
            str or None: If a path is found, it is returned. Otherwise None is returned.
        """
        hostport = self.registry

        for d in ('/etc/containers/certs.d', '/etc/docker/certs.d'):
            certs_dir = os.path.join(d, hostport)
            if os.path.isdir(certs_dir):
                return certs_dir

        return None

    def _find_cert(self, cert_dir):
        """
        Return a TLS client certificate to be used to authenticate to servers.

        Args:
            cert_dir (str or None): A directory to look for certs in. None indicates to use
               find_cert_dir() to find the path. Defaults to None.
        Returns:
            tuple or None: If no certificate is found, None is returned, otherwise, a 2-tuple
               is returned, the first element is the path to a certificate, the second element
               is the path to the matching key.
        Raises:
            RuntimeError: If a key is found without a matching certificate or vice versa.
        """
        if cert_dir is None:
            cert_dir = self._find_cert_dir()

        if cert_dir is None:
            return None

        for l in sorted(os.listdir(cert_dir)):
            if l.endswith('.cert'):
                certpath = os.path.join(cert_dir, l)
                keypath = certpath[:-5] + '.key'
                if not os.path.exists(keypath):
                    raise RuntimeError("Cannot find key file for {}".format(certpath))
                return (certpath, keypath)
            elif l.endswith('.key'):
                # Should have found <x>.cert first
                keypath = os.path.join(cert_dir, l)
                raise RuntimeError("Cannot find certificate file for {}".format(keypath))

        return None

    def _wrap_method(self, f, relative_url, *args, **kwargs):
        """
        Perform an HTTP request with appropriate options and fallback handling.

        This is used to implement methods like get, head, etc. It modifies
        kwargs, tries to do the operation, then if a TLS request fails and
        TLS validation is not required, tries again with a non-TLS URL.

        Args:
            f (callable): callback to actually perform the request.
            relative_url (str): URL relative to the toplevel hostname.
            kwargs: Additional arguments passed to requests.Session.get.
        Returns:
            requests.Response: The response object.
        """
        kwargs['auth'] = self.auth
        kwargs['cert'] = self.cert
        kwargs['verify'] = not self.insecure
        res = None
        if self._fallback:
            try:
                res = f(self._base + relative_url, *args, **kwargs)
                self._fallback = None  # don't fallback after one success
            except (SSLError, ConnectionError):
                self._base = self._fallback
                self._fallback = None
        if res is None:
            res = f(self._base + relative_url, *args, **kwargs)
        return res

    def get(self, relative_url, **kwargs):
        """
        Do a HTTP GET.

        Args:
            relative_url (str): URL relative to the toplevel hostname.
            kwargs: Additional arguments passed to requests.Session.get.
        Returns:
            requests.Response: The response object.
        """
        return self._wrap_method(self.session.get, relative_url, **kwargs)

    def head(self, relative_url, data=None, **kwargs):
        """
        Do a HTTP HEAD.

        Args:
            relative_url (str): URL relative to the toplevel hostname.
            kwargs: Additional arguments passed to requests.Session.head.
        Returns:
            requests.Response: The response object.
        """
        return self._wrap_method(self.session.head, relative_url, **kwargs)

    def post(self, relative_url, data=None, **kwargs):
        """
        Do a HTTP POST.

        Args:
            relative_url (str): URL relative to the toplevel hostname.
            data: Data to include with the post, as for requests.SESSION.
            kwargs: Additional arguments passed to requests.Session.post.
        Returns:
            requests.Response: The response object.
        """
        return self._wrap_method(self.session.post, relative_url, data=data, **kwargs)

    def put(self, relative_url, data=None, **kwargs):
        """
        Do a HTTP PUT.

        Args:
            relative_url (str): URL relative to the toplevel hostname.
            data: Data to include with the put, as for requests.SESSION.
            kwargs: Additional arguments passed to requests.Session.put.
        Returns:
            requests.Response: The response object.
        """
        return self._wrap_method(self.session.put, relative_url, data=data, **kwargs)


class ManifestInfo(object):
    """Information about a manifest downloaded from the registry."""

    def __init__(self, contents, digest, media_type, size):
        """
        Initialize the ManifestInfo.

        Args:
            contents (bytes): The contents.
            media_type (str): The type of the content.
            digest (str): The digest of the content.
            size (int): The size of the download, in bytes.
        """
        self.contents = contents
        self.digest = digest
        self.media_type = media_type
        self.size = size


def get_manifest(session, repository, ref):
    """
    Download a manifest from a registry.

    Args:
        session (RegistrySession): The session object.
        repository (str): The repository to download from.
        ref (str): A digest, or a tag.
    Returns:
        ManifestInfo: Information about the downloaded content.
    """
    logger.debug("%s: Retrieving manifest for %s:%s", session.registry, repository, ref)

    headers = {
        'Accept': ', '.join((
            MEDIA_TYPE_MANIFEST_V2,
            MEDIA_TYPE_LIST_V2,
            MEDIA_TYPE_OCI,
            MEDIA_TYPE_OCI_INDEX
        ))
    }

    url = '/v2/{}/manifests/{}'.format(repository, ref)
    response = session.get(url, headers=headers)
    response.raise_for_status()
    return ManifestInfo(response.content,
                        response.headers['Docker-Content-Digest'],
                        response.headers['Content-Type'],
                        int(response.headers['Content-Length']))


class DirectoryEndpoint(object):
    """
    The source or destination of a copy operation to a local directory.

    This is used only as a local intermediate, and for simplicity, the storage format is
    not exactly the same as for a dir:// reference as understood by skopeo.
    """

    def __init__(self, directory):
        """
        Initialize the DirectoryEndpoint.

        Args:
            directory (str): The path to the directory.
        """
        self.directory = directory

    def start_write(self):
        """Do setup before writing to the endpoint."""
        with open(os.path.join(self.directory, 'oci-layout'), 'w') as f:
            f.write('{"imageLayoutVersion": "1.0.0"}\n')

    def get_blob_path(self, digest):
        """
        Get the path that a blob with the given digest would be stored at.

        Args:
            digest (str): The digest of a blob to be stored.
        Returns:
            str: The full path where the blob would be stored.
        """
        algorithm, digest = digest.split(':', 2)
        return os.path.join(self.directory, 'blobs', algorithm, digest)

    def ensure_blob_path(self, digest):
        """
        Get path for a blob, creating parent directories if necessary.

        Args:
            digest (str): The digest of a blob to be stored.
        Returns:
            str: The full path where the blob would be stored.
        """
        path = self.get_blob_path(digest)

        parent = os.path.dirname(path)
        if not os.path.exists(parent):
            os.makedirs(parent)

        return path

    def get_blob(self, digest):
        """
        Return the contents of a blob object.

        Args:
            digest (str): The digest to retrieve.
        Returns:
            bytes: The contents of the blob.
        """
        with open(self.get_blob_path(digest), 'rb') as f:
            return f.read()

    def has_blob(self, digest):
        """
        Check if the repository has a blob with the given digest.

        Args:
            digest (str): The digest to check for.
        Returns:
            bool: True if the blob exists.
        """
        return os.path.exists(self.get_blob_path(digest))

    def write_blob(self, digest, contents):
        """
        Save a blob to the directory endpoint.

        Args:
            digest (str): The digest of the blob's contents.
            contents (bytes): The contents of the blob.
        """
        path = self.ensure_blob_path(digest)

        with open(path, 'wb') as f:
            f.write(contents)

    def get_manifest(self, digest=None, media_type=None):
        """
        Get a manifest from the endpoint.

        Arguments:
            digest (str): The digest of manifest to retrieve, or None to get the
               main manifest for the endpoint.
            media_type (str): The expected media type of the manifest.
        Returns:
            ManifestInfo: An object containing the contents of the manifest
               and other relevant information.
        """
        if digest is not None:
            contents = self.get_blob(digest)
        else:
            manifest_path = os.path.join(self.directory, 'manifest.json')
            if os.path.exists(manifest_path):
                with open(manifest_path, 'rb') as f:
                    contents = f.read()
                parsed = json.loads(contents)
                media_type = parsed.get('mediaType', MEDIA_TYPE_OCI)
            else:
                index_path = os.path.join(self.directory, 'index.json')
                with open(index_path, 'rb') as f:
                    contents = f.read()
                parsed = json.loads(contents)
                media_type = parsed.get('mediaType', MEDIA_TYPE_OCI_INDEX)

        return ManifestInfo(contents, digest, media_type, len(contents))

    def write_manifest(self, info, toplevel=False):
        """
        Store a manifest to the endpoint.

        Args:
            info (ManifestInfo): An object containing the contents of the manifest
                and other relevant information.
            toplevel (bool): If True, this should be the main manifest stored
                in the endpoint.
        """
        if not toplevel:
            self.write_blob(info.digest, info.contents)
        elif info.media_type in (MEDIA_TYPE_LIST_V2, MEDIA_TYPE_OCI_INDEX):
            with open(os.path.join(self.directory, 'index.json'), 'wb') as f:
                f.write(info.contents)
        else:
            with open(os.path.join(self.directory, 'manifest.json'), 'wb') as f:
                f.write(info.contents)


class RegistryEndpoint(object):
    """The source or destination of a copy operation to a docker registry."""

    def __init__(self, spec):
        """
        Initialize the RegistryEndpoint.

        Args:
            spec (RegistrySpec): A specification of registry, repository and tag.
        """
        self.session = spec.get_session()
        self.registry = spec.registry
        self.repo = spec.repo
        self.tag = spec.tag

    def start_write(self):
        """Do setup before writing to the endpoint."""
        pass

    def download_blob(self, digest, size, blob_path):
        """
        Download a blob from the registry to a local file.

        Args:
            digest (str): The digest of the blob to download.
            size (int): The size of blob.
            blob_path (str): The local path to write the blob to.
        """
        logger.info("%s: Downloading %s (size=%s)", self.registry, blob_path, size)

        url = "/v2/{}/blobs/{}".format(self.repo, digest)
        result = self.session.get(url, stream=True)
        result.raise_for_status()

        try:
            with open(blob_path, 'wb') as f:
                for block in result.iter_content(10 * 1024):
                    f.write(block)
        finally:
            result.close()

    def upload_blob(self, digest, size, blob_path):
        """
        Upload a blob from a local file to the registry.

        Args:
            digest (str): The digest of the blob to upload.
            size (int): The size of blob to upload.
            blob_path (str): The local path to read the blob from.
        """
        logger.info("%s: Uploading %s (size=%s)", self.registry, blob_path, size)

        url = "/v2/{}/blobs/uploads/".format(self.repo)
        result = self.session.post(url, data='')
        result.raise_for_status()

        if result.status_code != requests.codes.ACCEPTED:
            # if it was a failed response 4xx or 5xx then the raise_for_status()
            # would have raised - so it's a "successful" response - but by the docker v2 api,
            # a 202 ACCEPTED should be found here, not a 200 or other successful response.
            raise RuntimeError("Unexpected successful response %s (202 expected)",
                               result.status_code)

        upload_url = result.headers.get('Location')
        parsed = urlparse(upload_url)
        if parsed.query == '':
            query = 'digest=' + digest
        else:
            query = parsed.query + '&digest=' + digest
        relative = urlunparse(('', '', parsed.path, parsed.params, query, ''))

        headers = {
            'Content-Length': str(size),
            'Content-Type': 'application/octet-stream'
        }
        with open(blob_path, 'rb') as f:
            result = self.session.put(relative, data=f, headers=headers)

        result.raise_for_status()
        if result.status_code != requests.codes.CREATED:
            # if it was a failed response 4xx or 5xx then the raise_for_status()
            # would have raised - so it's a "successful" response - but by the docker v2 api,
            # a 202 CREATED should be found here, not a 200 or other successful response.
            raise RuntimeError("Unexpected successful response %s (201 expected)",
                               result.status_code)

    def link_blob(self, digest, src_repo):
        """
        Create a new reference to an object in another repository on the same registry.

        By using the "mount" operation from the docker protocol, we avoid having
        to download and upload data.

        Args:
            digest (str): The digest of the blob to create a new reference to.
            src_repo (str): Another repository in the same registry which already has a
               blob with the given digest.
        """
        logger.info("%s: Linking blob %s from %s to %s",
                    self.registry, digest, src_repo, self.repo)

        # Check that it exists in the source repository
        url = "/v2/{}/blobs/{}".format(src_repo, digest)
        result = self.session.head(url)
        result.raise_for_status()

        url = "/v2/{}/blobs/uploads/?mount={}&from={}".format(self.repo, digest, src_repo)
        result = self.session.post(url, data='')
        result.raise_for_status()

        if result.status_code != requests.codes.CREATED:
            # A 202-Accepted would mean that the source blob didn't exist and
            # we're starting an upload - but we've checked that above
            raise RuntimeError("Blob mount had unexpected status {}".format(result.status_code))

    def has_blob(self, digest):
        """
        Check if the repository has a blob with the given digest.

        Args:
            digest (str): The digest to check for.
        Returns:
            bool: True if the blob exists.
        """
        url = "/v2/{}/blobs/{}".format(self.repo, digest)
        result = self.session.head(url, stream=True)
        if result.status_code == 404:
            return False
        result.raise_for_status()
        return True

    def get_manifest(self, digest=None, media_type=None):
        """
        Get a manifest from the endpoint.

        Args:
            digest (str): The digest of manifest to retrieve, or None to get the
               main manifest for the endpoint.
            media_type (str): The expected media type of the manifest.
        Returns:
            ManifestInfo: An object containing the contents of the manifest
               and other relevant information.
        """
        if digest is None:
            return get_manifest(self.session, self.repo, self.tag)
        else:
            return get_manifest(self.session, self.repo, digest)

    def write_manifest(self, info, toplevel=False):
        """
        Store a manifest to the endpoint.

        Args:
            info (ManifestInfo): An object containing the contents of the manifest
                and other relevant information.
            toplevel (bool): If True, this should be the main manifest stored
                in the endpoint.
        """
        if toplevel:
            ref = self.tag
        else:
            ref = info.digest

        logger.info("%s: Storing manifest as %s", self.registry, ref)

        url = '/v2/{}/manifests/{}'.format(self.repo, ref)
        headers = {'Content-Type': info.media_type}
        response = self.session.put(url, data=info.contents, headers=headers)
        response.raise_for_status()


class Copier(object):
    """
    Implements a copy operation between different endpoints.

    As currently implemented, only copying to/from a registry and a directory
    or within the *same* registry is implemented.
    """

    def __init__(self, src, dest):
        """Initialize the Copier.

        Args:
            src (str): The source endpoint.
            dest (str): The destination endpoint.
        """
        self.src = src
        self.dest = dest

    def _copy_blob(self, digest, size):
        """
        Copy a blob with given digest and size from the source to the destination.

        Args:
            digest (str): The digest of the blob to copy.
            size (int): The size of the blob to copy.
        """
        if self.dest.has_blob(digest):
            return

        if isinstance(self.src, RegistryEndpoint) and isinstance(self.dest, DirectoryEndpoint):
            self.src.download_blob(digest, size, self.dest.ensure_blob_path(digest))
        elif isinstance(self.src, DirectoryEndpoint) and isinstance(self.dest, RegistryEndpoint):
            self.dest.upload_blob(digest, size, self.src.get_blob_path(digest))
        else:
            # The copy() function below ensures that the following two asserts don't fail.
            assert (isinstance(self.src, RegistryEndpoint)
                    and isinstance(self.dest, RegistryEndpoint))
            assert self.src.registry == self.dest.registry

            self.dest.link_blob(digest, self.src.repo)

        # Other forms of copying are not needed currently, and not implemented

    def _copy_manifest(self, info, toplevel=False):
        """
        Copy the manifest referenced by info from the source to destination.

        Args:
            info (ManifestInfo): References the manifest to be copied.
            toplevel (bool): If True, this should be the main manifest referenced in the repository.
                Defaults to False.
        Raises:
            RuntimeError: If the referenced media type is not supported by this client.
        """
        references = []
        if info.media_type in (MEDIA_TYPE_MANIFEST_V2, MEDIA_TYPE_OCI):
            manifest = json.loads(info.contents)
            references.append((manifest['config']['digest'], manifest['config']['size']))
            for layer in manifest['layers']:
                references.append((layer['digest'], layer['size']))
        else:
            raise RuntimeError("Unhandled media type %s", info.media_type)

        for digest, size in references:
            self._copy_blob(digest, size)

        self.dest.write_manifest(info, toplevel=toplevel)

    def copy(self):
        """Perform the copy operation."""
        self.dest.start_write()
        info = self.src.get_manifest()
        if info.media_type in (MEDIA_TYPE_MANIFEST_V2, MEDIA_TYPE_OCI):
            self._copy_manifest(info, toplevel=True)
        elif info.media_type in (MEDIA_TYPE_LIST_V2, MEDIA_TYPE_OCI_INDEX):
            manifest = json.loads(info.contents)
            for m in manifest['manifests']:
                referenced = self.src.get_manifest(digest=m['digest'], media_type=m['mediaType'])
                self._copy_manifest(referenced)
            self.dest.write_manifest(info, toplevel=True)

        else:
            raise RuntimeError("Unhandled media type %s", info.media_type)


@main.command()
@click.option('--src-creds', '--screds', 'src_creds', metavar='USERNAME[:PASSWORD]',
              help='Use USERNAME[:PASSWORD] for accessing the source registry')
@click.option('--src-tls-verify', type=bool, default=True,
              help=('require HTTPS and verify certificates when talking to the '
                    'container source registry (defaults to true)'))
@click.option('--src-cert-dir', metavar='PATH',
              help=('use certificates at PATH (*.crt, *.cert, *.key) to connect to the '
                    'source registry'))
@click.option('--dest-creds', '--dcreds', 'dest_creds', metavar='USERNAME[:PASSWORD]',
              help='Use USERNAME[:PASSWORD] for accessing the destination registry')
@click.option('--dest-tls-verify', type=bool, default=True,
              help=('require HTTPS and verify certificates when talking to the '
                    'container destination registry (defaults to true)'))
@click.option('--dest-cert-dir', metavar='PATH',
              help=('use certificates at PATH (*.crt, *.cert, *.key) to connect to the '
                    'destination registry'))
@click.argument('src', metavar='SOURCE-IMAGE-NAME')
@click.argument('dest', metavar='DEST-IMAGE-NAME')
def copy(src, dest, src_creds, src_tls_verify, src_cert_dir, dest_creds, dest_tls_verify,
         dest_cert_dir):
    """Copy an image from one location to another."""
    src = parse_spec(src, src_creds, src_tls_verify, src_cert_dir)
    dest = parse_spec(dest, dest_creds, dest_tls_verify, dest_cert_dir)

    # Copier._copy_blob() assumes this:
    # - The src and dest registries are of types RegistryEndpoint or DirectoryEndpoint, at least one
    #   must be a RegistryEndpoint.
    # - If both are a RegistryEndpoint, they must be the same so linking is possible, therefore we
    #   copy src reg -> local dir -> dest reg if this isn't the case.
    if src.registry != dest.registry:
        tempdir = tempfile.mkdtemp()
        try:
            tmp = DirectoryEndpoint(tempdir)
            Copier(src.get_endpoint(), tmp).copy()
            Copier(tmp, dest.get_endpoint()).copy()
        finally:
            shutil.rmtree(tempdir)
    else:
        Copier(src.get_endpoint(), dest.get_endpoint()).copy()


if __name__ == '__main__':
    main()
