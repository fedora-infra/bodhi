# Copyright © 2018-2019 Red Hat, Inc.
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
"""This module contains tests for bodhi.server.scripts.skopeo_lite."""

from base64 import b64encode
from contextlib import contextmanager
from urllib.parse import urlparse
from unittest import mock
import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid

from click import testing
import pytest
import responses
import requests

from bodhi.server.scripts import skopeo_lite
from bodhi.server.scripts.skopeo_lite import (MEDIA_TYPE_MANIFEST_V2, MEDIA_TYPE_LIST_V2,
                                              MEDIA_TYPE_OCI, MEDIA_TYPE_OCI_INDEX)


REGISTRY_V1 = 'registry_v1.example.com'
REGISTRY_V2 = 'registry_v2.example.com'
OTHER_V2 = 'registry.example.com:5001'

all_registry_conf = {
    REGISTRY_V2: {'version': 'v2', 'insecure': True},
    OTHER_V2: {'version': 'v2', 'insecure': False},
}


def registry_hostname(registry):
    """
    Strip a reference to a registry to just the hostname:port
    """
    if registry.startswith('http:') or registry.startswith('https:'):
        return urlparse(registry).netloc
    else:
        return registry


def to_bytes(value):
    if isinstance(value, bytes):
        return value
    else:
        return value.encode('utf-8')


def to_text(value):
    if isinstance(value, str):
        return value
    else:
        return str(value, 'utf-8')


def make_digest(blob):
    # Abbreviate the hexdigest for readability of debugging output if things fail
    return 'sha256:' + hashlib.sha256(to_bytes(blob)).hexdigest()[0:10]


class MockRegistry(object):
    """
    This class mocks a subset of the v2 Docker Registry protocol. It also has methods to inject
    and test content in the registry.
    """
    def __init__(self, registry, insecure=False, required_creds=None, flags=''):
        self.hostname = registry_hostname(registry)
        self.insecure = insecure
        self.repos = {}
        self.required_creds = required_creds
        self.flags = flags
        self._add_pattern(responses.GET, r'/v2/(.*)/manifests/([^/]+)',
                          self._get_manifest)
        self._add_pattern(responses.HEAD, r'/v2/(.*)/manifests/([^/]+)',
                          self._get_manifest)
        self._add_pattern(responses.PUT, r'/v2/(.*)/manifests/([^/]+)',
                          self._put_manifest)
        self._add_pattern(responses.GET, r'/v2/(.*)/blobs/([^/]+)',
                          self._get_blob)
        self._add_pattern(responses.HEAD, r'/v2/(.*)/blobs/([^/]+)',
                          self._get_blob)
        self._add_pattern(responses.POST, r'/v2/(.*)/blobs/uploads/',
                          self._post_blob)
        self._add_pattern(responses.PUT, r'/v2/(.*)/blobs/uploads/([^?]*)\?digest=(.*)',
                          self._put_blob)
        self._add_pattern(responses.PUT, r'/v2/(.*)/blobs/uploads/([^?]*)\?dummy=1&digest=(.*)',
                          self._put_blob)
        self._add_pattern(responses.POST, r'/v2/(.*)/blobs/uploads/\?mount=([^&]+)&from=(.+)',
                          self._mount_blob)

    def get_repo(self, name):
        return self.repos.setdefault(name, {
            'blobs': {},
            'manifests': {},
            'tags': {},
            'uploads': {},
        })

    def add_blob(self, name, blob):
        repo = self.get_repo(name)
        digest = make_digest(blob)
        repo['blobs'][digest] = blob
        return digest

    def get_blob(self, name, digest):
        return self.get_repo(name)['blobs'][digest]

    def add_manifest(self, name, ref, manifest):
        repo = self.get_repo(name)
        digest = make_digest(manifest)
        repo['manifests'][digest] = manifest
        if ref is None:
            pass
        elif ref.startswith('sha256:'):
            assert ref == digest
        else:
            repo['tags'][ref] = digest
        return digest

    def get_manifest(self, name, ref):
        repo = self.get_repo(name)
        if not ref.startswith('sha256:'):
            ref = repo['tags'][ref]
        return repo['manifests'][ref]

    def _check_creds(self, req):
        if self.required_creds:
            username, password = self.required_creds

            auth = req.headers['Authorization'].strip().split()
            assert auth[0] == 'Basic'
            assert to_bytes(auth[1]) == b64encode(to_bytes(username + ':' + password))

    def _add_pattern(self, method, pattern, callback):
        if self.insecure:
            url = 'http://' + self.hostname
        else:
            url = 'https://' + self.hostname
        pat = re.compile('^' + url + pattern + '$')

        def do_it(req):
            self._check_creds(req)

            status, headers, body = callback(req, *(pat.match(req.url).groups()))
            if method == responses.HEAD:
                return status, headers, ''
            else:
                return status, headers, body

        responses.add_callback(method, pat, do_it, match_querystring=True)

    def _get_manifest(self, req, name, ref):
        repo = self.get_repo(name)
        if not ref.startswith('sha256:'):
            try:
                ref = repo['tags'][ref]
            except KeyError:
                return (requests.codes.NOT_FOUND, {}, {'error': 'NOT_FOUND'})

        try:
            blob = repo['manifests'][ref]
        except KeyError:
            return (requests.codes.NOT_FOUND, {}, {'error': 'NOT_FOUND'})

        decoded = json.loads(to_text(blob))
        content_type = decoded.get('mediaType')
        if content_type is None:  # OCI
            if decoded.get('manifests') is not None:
                content_type = MEDIA_TYPE_OCI_INDEX
            else:
                content_type = MEDIA_TYPE_OCI

        accepts = re.split(r'\s*,\s*', req.headers['Accept'])
        assert content_type in accepts

        if 'bad_index_content_type' in self.flags:
            if content_type == MEDIA_TYPE_OCI_INDEX:
                content_type = 'application/json'
        if 'bad_content_type' in self.flags:
            if content_type == MEDIA_TYPE_OCI:
                content_type = 'application/json'

        headers = {
            'Docker-Content-Digest': ref,
            'Content-Type': content_type,
            'Content-Length': str(len(blob)),
        }
        return (200, headers, blob)

    def _put_manifest(self, req, name, ref):
        try:
            json.loads(to_text(req.body))
        except ValueError:
            return (400, {}, {'error': 'BAD_MANIFEST'})

        self.add_manifest(name, ref, req.body)
        return (200, {}, '')

    def _get_blob(self, req, name, digest):
        repo = self.get_repo(name)
        assert digest.startswith('sha256:')

        try:
            blob = repo['blobs'][digest]
        except KeyError:
            return (requests.codes.NOT_FOUND, {}, {'error': 'NOT_FOUND'})

        headers = {
            'Docker-Content-Digest': digest,
            'Content-Type': 'application/json',
            'Content-Length': str(len(blob)),
        }
        return (200, headers, blob)

    def _post_blob(self, req, name):
        repo = self.get_repo(name)
        uuid_str = str(uuid.uuid4())
        repo['uploads'][uuid_str] = ''

        if 'include_query_parameters' in self.flags:
            location = '/v2/{}/blobs/uploads/{}?dummy=1'.format(name, uuid_str)
        else:
            location = '/v2/{}/blobs/uploads/{}'.format(name, uuid_str)

        headers = {
            'Location': location,
            'Range': 'bytes=0-0',
            'Content-Length': '0',
            'Docker-Upload-UUID': uuid_str,
        }
        return (200 if 'bad_post_status' in self.flags else 202, headers, '')

    def _put_blob(self, req, name, uuid, digest):
        repo = self.get_repo(name)

        assert uuid in repo['uploads']
        del repo['uploads'][uuid]

        if isinstance(req.body, (bytes, str)):
            blob = req.body
        else:
            blob = req.body.read()

        added_digest = self.add_blob(name, blob)
        assert added_digest == digest

        headers = {
            'Location': '/v2/{}/blobs/{}'.format(name, digest),
            'Docker-Content-Digest': added_digest,
        }

        return (200 if 'bad_put_status' in self.flags else 201, headers, '')

    def _mount_blob(self, req, target_name, digest, source_name):
        source_repo = self.get_repo(source_name)
        target_repo = self.get_repo(target_name)

        try:
            target_repo['blobs'][digest] = source_repo['blobs'][digest]
            headers = {
                'Location': '/v2/{}/blobs/{}'.format(target_name, digest),
                'Docker-Content-Digest': digest,
            }
            return (200 if 'bad_mount_status' in self.flags else 201, headers, '')
        except KeyError:
            headers = {
                'Location': '/v2/{}/blobs/uploads/some-uuid'.format(target_name),
                'Docker-Upload-UUID': 'some-uuid',
            }
            return (202, headers, '')

    def add_fake_image(self, name, tag, content_type,
                       arch='amd64'):
        layer_digest = self.add_blob(name, 'layer-' + arch)
        layer_size = len(to_bytes('layer-' + arch))

        config = {
            'architecture': arch,
            'os': 'linux',
        }
        config_bytes = to_bytes(json.dumps(config))
        config_digest = self.add_blob(name, config_bytes)
        config_size = len(config_bytes)

        if content_type in (MEDIA_TYPE_MANIFEST_V2, MEDIA_TYPE_LIST_V2):
            manifest = {
                'schemaVersion': 2,
                'mediaType': MEDIA_TYPE_MANIFEST_V2,
                'config': {
                    'mediaType': 'application/vnd.docker.container.image.v1+json',
                    'digest': config_digest,
                    'size': config_size,
                },
                'layers': [{
                    'mediaType': 'application/vnd.docker.image.rootfs.diff.tar.gzip',
                    'digest': layer_digest,
                    'size': layer_size,
                }]
            }

            if content_type == MEDIA_TYPE_LIST_V2:
                manifest_bytes = to_bytes(json.dumps(manifest))
                manifest_digest = self.add_manifest(name, None, manifest_bytes)

                manifest = {
                    'schemaVersion': 2,
                    'mediaType': MEDIA_TYPE_LIST_V2,
                    'manifests': [{
                        'mediaType': MEDIA_TYPE_MANIFEST_V2,
                        'size': len(manifest_bytes),
                        'digest': manifest_digest,
                        'platform': {
                            'architecture': arch,
                            'os': 'linux',
                        }
                    }]
                }
        else:
            manifest = {
                'schemaVersion': 2,
                'mediaType': MEDIA_TYPE_OCI,
                'config': {
                    'mediaType': 'application/vnd.oci.image.config.v1+json',
                    'digest': config_digest,
                    'size': config_size,
                },
                'layers': [{
                    'mediaType': 'application/vnd.oci.image.layer.v1.tar',
                    'digest': layer_digest,
                    'size': layer_size,
                }]
            }

            if content_type == MEDIA_TYPE_OCI_INDEX:
                manifest_bytes = to_bytes(json.dumps(manifest))
                manifest_digest = self.add_manifest(name, None, manifest_bytes)

                manifest = {
                    'schemaVersion': 2,
                    'manifests': [{
                        'mediaType': MEDIA_TYPE_OCI,
                        'size': len(manifest_bytes),
                        'digest': manifest_digest,
                        'platform': {
                            'architecture': arch,
                            'os': 'linux',
                        }
                    }]
                }

        manifest_bytes = to_bytes(json.dumps(manifest))
        return self.add_manifest(name, tag, manifest_bytes)

    def check_fake_image(self, name, tag, digest, content_type):
        manifest_bytes = self.get_manifest(name, tag)
        assert make_digest(manifest_bytes) == digest

        manifest = json.loads(to_text(manifest_bytes))
        if content_type in (MEDIA_TYPE_LIST_V2, MEDIA_TYPE_OCI_INDEX):
            manifest_digest = manifest['manifests'][0]['digest']
            manifest_bytes = self.get_manifest(name, manifest_digest)
            manifest = json.loads(to_text(manifest_bytes))

        config_digest = manifest['config']['digest']
        assert make_digest(self.get_blob(name, config_digest)) == config_digest

        layer_digest = manifest['layers'][0]['digest']
        assert make_digest(self.get_blob(name, layer_digest)) == layer_digest


@responses.activate
@pytest.mark.parametrize('content_type',
                         (MEDIA_TYPE_OCI, MEDIA_TYPE_OCI_INDEX,
                          MEDIA_TYPE_MANIFEST_V2, MEDIA_TYPE_LIST_V2))
def test_skopeo_copy_basic(content_type):
    """
    Test copying from one server to another
    """
    runner = testing.CliRunner()

    reg1 = MockRegistry('registry1.example.com')
    reg2 = MockRegistry('registry2.example.com')
    digest = reg1.add_fake_image('repo1', 'latest', content_type)

    result = runner.invoke(
        skopeo_lite.copy,
        ['docker://registry1.example.com/repo1:latest',
         'docker://registry2.example.com/repo2:latest'],
        catch_exceptions=False)

    assert result.exit_code == 0

    reg2.check_fake_image('repo2', 'latest', digest, content_type)


@responses.activate
@pytest.mark.parametrize('content_type',
                         (MEDIA_TYPE_OCI, MEDIA_TYPE_OCI_INDEX,
                          MEDIA_TYPE_MANIFEST_V2, MEDIA_TYPE_LIST_V2))
def test_skopeo_copy_link(content_type):
    """
    Testing copying on the same server, avoiding download/upload
    """
    runner = testing.CliRunner()

    reg1 = MockRegistry('registry1.example.com')
    digest = reg1.add_fake_image('repo1', 'latest', content_type)

    result = runner.invoke(
        skopeo_lite.copy,
        ['docker://registry1.example.com/repo1:latest',
         'docker://registry1.example.com/repo2:latest'],
        catch_exceptions=False)

    assert result.exit_code == 0

    reg1.check_fake_image('repo2', 'latest', digest, content_type)


@responses.activate
@pytest.mark.parametrize('content_type',
                         (MEDIA_TYPE_OCI, MEDIA_TYPE_OCI_INDEX,
                          MEDIA_TYPE_MANIFEST_V2, MEDIA_TYPE_LIST_V2))
def test_skopeo_copy_tag(content_type):
    """
    Testing copying within the same repo - creating a new tag for an existing image
    """
    runner = testing.CliRunner()

    reg1 = MockRegistry('registry1.example.com')
    digest = reg1.add_fake_image('repo1', '1.2.3', content_type)

    # No tag should be the same as :latest
    result = runner.invoke(
        skopeo_lite.copy,
        ['docker://registry1.example.com/repo1:1.2.3', 'docker://registry1.example.com/repo1'],
        catch_exceptions=False)

    assert result.exit_code == 0

    reg1.check_fake_image('repo1', 'latest', digest, content_type)


@responses.activate
@pytest.mark.parametrize('insecure', (True, False))
def test_skopeo_copy_insecure(insecure):
    """
    Testing falling back to HTTP when talking to a server
    """
    runner = testing.CliRunner()

    content_type = MEDIA_TYPE_MANIFEST_V2
    reg1 = MockRegistry('registry1.example.com', insecure=insecure)
    digest = reg1.add_fake_image('repo1', '1.2.3', content_type)

    result = runner.invoke(
        skopeo_lite.copy,
        ['--src-tls-verify', 'false',
         '--dest-tls-verify', 'false',
         'docker://registry1.example.com/repo1:1.2.3',
         'docker://registry1.example.com/repo1:latest'],
        catch_exceptions=False)

    assert result.exit_code == 0

    reg1.check_fake_image('repo1', 'latest', digest, content_type)


@responses.activate
def test_skopeo_copy_username_password():
    """
    Testing authentication with username and password
    """
    runner = testing.CliRunner()

    content_type = MEDIA_TYPE_MANIFEST_V2
    reg1 = MockRegistry('registry1.example.com', required_creds=('someuser', 'somepassword'))
    reg2 = MockRegistry('registry2.example.com', required_creds=('otheruser', 'otherpassword'))
    digest = reg1.add_fake_image('repo1', 'latest', content_type)

    result = runner.invoke(
        skopeo_lite.copy,
        ['--src-creds', 'someuser:somepassword',
         '--dest-creds', 'otheruser:otherpassword',
         'docker://registry1.example.com/repo1:latest',
         'docker://registry2.example.com/repo2:latest'],
        catch_exceptions=False)

    assert result.exit_code == 0

    reg2.check_fake_image('repo2', 'latest', digest, content_type)


@contextmanager
def check_certificates(get_cert=None, put_cert=None):
    old_get = requests.Session.get
    old_put = requests.Session.put

    def checked_get(self, *args, **kwargs):
        if kwargs.get('cert') != get_cert:
            raise RuntimeError("Wrong/missing cert for GET")

        return old_get(self, *args, **kwargs)

    def checked_put(self, *args, **kwargs):
        if kwargs.get('cert') != put_cert:
            raise RuntimeError("Wrong/missing cert for PUT")

        return old_put(self, *args, **kwargs)

    with mock.patch('requests.Session.get', autospec=True, side_effect=checked_get):
        with mock.patch('requests.Session.put', autospec=True, side_effect=checked_put):
            yield


@responses.activate
@pytest.mark.parametrize(('breakage', 'error'), [
    (None, None),
    ('missing_cert', 'Cannot find certificate file'),
    ('missing_key', 'Cannot find key file'),
    ('missing_cert_and_key', 'Wrong/missing cert'),
])
def test_skopeo_copy_cert(breakage, error):
    """
    Test authentication with a certificate
    """
    runner = testing.CliRunner()

    certdir1 = tempfile.mkdtemp()
    certdir2 = tempfile.mkdtemp()
    try:
        certs = {}
        for certdir, reg in ((certdir1, 'registry1.example.com'),
                             (certdir2, 'registry2.example.com')):
            cert = os.path.join(certdir, reg + '.cert')
            if breakage not in ('missing_cert', 'missing_cert_and_key'):
                with open(cert, 'w'):
                    pass
            key = os.path.join(certdir, reg + '.key')
            if breakage not in ('missing_key', 'missing_cert_and_key'):
                with open(key, 'w'):
                    pass
            certs[reg] = (cert, key)
            # Ensure RegistrySession._find_cert() encounters a file to skip
            # over.
            if not breakage and reg == 'registry1.example.com':
                with open(os.path.join(certdir, 'dummy'), 'w'):
                    pass

        content_type = MEDIA_TYPE_MANIFEST_V2
        reg1 = MockRegistry('registry1.example.com')
        reg2 = MockRegistry('registry2.example.com')
        digest = reg1.add_fake_image('repo1', 'latest', content_type)

        with check_certificates(get_cert=certs['registry1.example.com'],
                                put_cert=certs['registry2.example.com']):
            args = ['--src-cert-dir', certdir1,
                    '--dest-cert-dir', certdir2,
                    'docker://registry1.example.com/repo1:latest',
                    'docker://registry2.example.com/repo2:latest']

            if breakage is None:
                result = runner.invoke(
                    skopeo_lite.copy,
                    args,
                    catch_exceptions=False)

                assert result.exit_code == 0
                reg2.check_fake_image('repo2', 'latest', digest, content_type)
            else:
                with pytest.raises(Exception) as excinfo:
                    runner.invoke(
                        skopeo_lite.copy,
                        args,
                        catch_exceptions=False)
                assert error in str(excinfo.value)
    finally:
        shutil.rmtree(certdir1)
        shutil.rmtree(certdir2)


@contextmanager
def mock_system_certs():
    old_isdir = os.path.isdir
    old_listdir = os.listdir
    old_exists = os.path.exists

    def isdir(path):
        if isinstance(path, str) and path.startswith('/etc/'):
            return path in ('/etc/docker/certs.d/registry1.example.com',
                            '/etc/docker/certs.d/registry2.example.com')
        else:
            return old_isdir(path)

    def listdir(path):
        if isinstance(path, str) and path.startswith('/etc/'):
            if path in ('/etc/docker/certs.d/registry1.example.com',
                        '/etc/docker/certs.d/registry2.example.com'):
                return ('client.cert', 'client.key')
            else:
                return None
        else:
            return old_listdir(path)

    def exists(path):
        if isinstance(path, str) and path.startswith('/etc/'):
            return path in ('/etc/docker/certs.d/registry1.example.com/client.cert',
                            '/etc/docker/certs.d/registry1.example.com/client.key',
                            '/etc/docker/certs.d/registry2.example.com/client.cert',
                            '/etc/docker/certs.d/registry2.example.com/client.key')
        else:
            return old_exists(path)

    with mock.patch('os.path.isdir', side_effect=isdir):
        with mock.patch('os.listdir', side_effect=listdir):
            with mock.patch('os.path.exists', side_effect=exists):
                yield


@responses.activate
def test_skopeo_copy_system_cert():
    """
    Test using a certificate from a system directory
    """
    runner = testing.CliRunner()

    reg1 = MockRegistry('registry1.example.com')
    MockRegistry('registry2.example.com')
    reg1.add_fake_image('repo1', 'latest', MEDIA_TYPE_MANIFEST_V2)

    with mock_system_certs():
        with check_certificates(get_cert=('/etc/docker/certs.d/registry1.example.com/client.cert',
                                          '/etc/docker/certs.d/registry1.example.com/client.key'),
                                put_cert=('/etc/docker/certs.d/registry2.example.com/client.cert',
                                          '/etc/docker/certs.d/registry2.example.com/client.key')):
            runner.invoke(
                skopeo_lite.copy,
                ['docker://registry1.example.com/repo1:latest',
                 'docker://registry2.example.com/repo2:latest'],
                catch_exceptions=False)


@responses.activate
@pytest.mark.parametrize(('src', 'dest', 'error'), [
    ('docker://registry1.example.com/repo1:latest', 'badtype://registry2.example.com/repo2:latest',
     'Unknown source/destination'),
    ('docker://registry1.example.com/repo1:latest', 'docker:registry1.example.com/repo2:latest',
     'Registry specification should be docker://REGISTRY/PATH'),
    ('docker://registry1.example.com/repo1:latest', 'docker://registry2.example.com',
     'Registry specification should be docker://REGISTRY/PATH'),
])
def test_skopeo_copy_cli_errors(src, dest, error):
    """
    Test errors triggered from bad command line arguments
    """
    runner = testing.CliRunner()

    options = []

    result = runner.invoke(
        skopeo_lite.copy,
        options + [src, dest])

    assert error in result.output
    assert result.exit_code != 0


@responses.activate
@pytest.mark.parametrize(('src', 'dest', 'flags1', 'flags2', 'error'), [
    ('docker://registry1.example.com/repo1:latest', 'docker://registry2.example.com/repo2:latest',
     '', 'bad_put_status',
     'Unexpected successful response'),
    ('docker://registry1.example.com/repo1:latest', 'docker://registry2.example.com/repo2:latest',
     '', 'bad_post_status',
     'Unexpected successful response'),
    ('docker://registry1.example.com/repo1:latest', 'docker://registry1.example.com/repo2:latest',
     'bad_mount_status', '',
     'Blob mount had unexpected status'),
    ('docker://registry1.example.com/repo1:latest', 'docker://registry2.example.com/repo2:latest',
     'bad_index_content_type', '',
     'Unhandled media type'),
    ('docker://registry1.example.com/repo1:latest', 'docker://registry2.example.com/repo2:latest',
     'bad_content_type', '',
     'Unhandled media type'),
    ('docker://registry1.example.com/repo1:latest', 'docker://registry2.example.com/repo2:latest',
     '', 'include_query_parameters',
     None),
])
def test_skopeo_copy_protocol(src, dest, flags1, flags2, error):
    """
    Tests various error and other code paths related to variations in server responses; the
    flags argument to the MockRegistry constructor is used to modify server behavior.
    """
    runner = testing.CliRunner()

    content_type = MEDIA_TYPE_OCI_INDEX

    reg1 = MockRegistry('registry1.example.com', flags=flags1)
    MockRegistry('registry2.example.com', flags=flags2)
    reg1.add_fake_image('repo1', 'latest', content_type)

    if error is not None:
        with pytest.raises(Exception) as excinfo:
            runner.invoke(
                skopeo_lite.copy,
                [src, dest],
                catch_exceptions=False)

        assert error in str(excinfo.value)
    else:
        result = runner.invoke(
            skopeo_lite.copy,
            [src, dest])

        assert result.exit_code == 0
