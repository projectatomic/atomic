import requests
import json
import os
from base64 import b64decode
from . import util
import hashlib


try:
    from urllib.request import parse_http_list, parse_keqv_list
except ImportError:
    from urllib2 import parse_http_list, parse_keqv_list #pylint: disable=import-error


def jose_base64_urldecode(in_str):
    in_str = in_str.replace("\n", "")
    in_str = in_str.replace(" ", "")
    str_len = len(in_str) % 4
    if str_len not in [0, 2, 3]:
        raise ValueError("{} is an illegal base64url string".format(in_str))
    if str_len == 2:
        in_str += "=="
    elif str_len == 3:
        in_str += "="
    return b64decode(in_str)


class RegistryConnection():

    def __init__(self, debug):
        self.headers = {
            'Accept': '[application/vnd.oci.image.manifest.v1+json,'
                      'application/vnd.docker.distribution.manifest.v2+json,'
                      'application/vnd.docker.distribution.manifest.v1+prettyjws,'
                      'application/vnd.docker.distribution.manifest.v1+json]'
        }
        self.auth_headers = {}
        self.hostname = None
        self.scheme = None
        self.needs_auth = False
        self.token = None
        self.token_realm = None
        self.token_service = None
        self.token_scope = None
        self._debug = debug
        self.orig_manifest = None
        self.manifest_json = None
        self.whatever_json = None
        self.tag_json = None
        self.registry = None
        self.local_tokens = None
        self.schema_version = None
        self.pinged = False
        self.verify = True
        self.port = None

    def inspect_schema1(self, name, tag):
        v1compat = json.loads(self.manifest_json['history'][0]['v1Compatibility'])
        return {
            'Name': name,
            'Tag': tag,
            'Digest': "sha256:{}".format(self.get_digest()),
            'RepoTags':  self.tag_json['tags'],
            'Created': v1compat['created'],
            'DockerVersion': v1compat['docker_version'],
            'Labels': v1compat['config']['Labels'],
            'Architecture': self.manifest_json['architecture'],
            'Os': v1compat['os'],
            'Layers': [x['blobSum'] for x in self.manifest_json['fsLayers']][::-1]
            }

    def inspect_schema2(self, name, tag):
        return {
            'Name': name,
            'Tag': tag,
            'Digest': "sha256:{}".format(self.get_digest()),
            'RepoTags':  self.tag_json['tags'],
            'Created':  self.whatever_json['created'],
            'DockerVersion': self.whatever_json['docker_version'],
            'Labels':  self.whatever_json['config']['Labels'],
            'Architecture': self.whatever_json['architecture'],
            'Os': self.whatever_json['os'],
            'Layers': [x['digest'] for x in self.manifest_json['layers']][::-1]
        }

    def get_digest(self):
        if 'signatures' in self.manifest_json:
            return self._get_digest_from_signature()
        else:
            return hashlib.sha256(self.orig_manifest.encode('utf-8')).hexdigest()

    def _get_digest_from_signature(self):
        for i in self.manifest_json['signatures']:
            _protected = i['protected']
            protected_js = json.loads(jose_base64_urldecode(_protected).decode('utf-8'))
            format_length = protected_js['formatLength']
            format_tail = jose_base64_urldecode(protected_js['formatTail']).decode('utf-8')
            orig = [ord(x) for x in self.orig_manifest]
            formatted = orig[:format_length] + [ord(x) for x in format_tail]
            return hashlib.sha256("".join([chr(x) for x in formatted]).encode('utf-8')).hexdigest()

    @staticmethod
    def load_local_tokens():
        tokens = {}
        token_file_name = os.path.expanduser('~/.docker/config.json')
        if not os.path.exists(token_file_name):
            return {}
        with open(token_file_name) as token_file:
            token_data = json.load(token_file)
        for registry in token_data['auths']:
            tokens[registry] = token_data['auths'][registry]['auth']
        return tokens

    def get(self, url, skip_auth=False):
        if self.needs_auth and not skip_auth:
            if not self.token:
                self.get_token()
            headers = self.get_auth_headers()
        else:
            headers = self.headers

        self.debug("GET_URL: %s" % url)
        self.debug("GET_HEADER: %s" % headers)
        self.debug("GET_VERIFY: %s" % self.verify)
        results = requests.get(url, headers=headers, verify=self.verify)
        if results.reason == "Unauthorized" and self.needs_auth:
            # Auth registries dont tell us if credentials are bad or the GET URL is bad
            raise RegistryAuthError("Unable to authenticate to {} or repository, image, "
                                    "or tags names are bad".format(self.registry))
        return results

    def _create_self_auth_headers(self):
        headers = self.headers.copy()
        headers['Authorization'] = "Bearer {}".format(self.token)
        self.auth_headers = headers

    def get_auth_headers(self):
        if len(self.auth_headers) is 0:
            self._create_self_auth_headers()
        return self.auth_headers

    def debug(self, msg):
        if self._debug:
            util.write_out(msg)

    @staticmethod
    def get_components_from_bearer(header):
        _, _, value = header.partition("Bearer")
        opts = parse_keqv_list(parse_http_list(value)) if value else None
        return opts.get('realm', None), opts.get('service', None), opts.get('scope', None)

    def set_token_from_header(self, bearer):
        realm, service, scope = self.get_components_from_bearer(bearer)
        self._set_token(realm, service, scope)

    def _set_token(self, realm, service, scope):
        self.token_realm = realm
        self.token_service = service
        self.token_scope = scope

    def get_token(self):
        local_tokens = self.local_tokens if self.local_tokens else self.load_local_tokens()
        if self.token_scope and self.token_service:
            url = '{}?service={}&scope={}'.format(self.token_realm, self.token_service, self.token_scope)
            self.token = self.get(url, skip_auth=True).json()['token']
        elif not self.token_scope and not self.token_service and self.hostname in local_tokens:
            host_token = (local_tokens[self.hostname]).encode()
            self.token = str(b64decode(host_token)).split(':')[-1]
        else:
            raise RegistryAuthError("Failed to obtain token")
        self.debug("Set token to {}".format(self.token))

    def set_token_scope(self, repo, image):
        self.token_scope = "repository:{}/{}:pull".format(repo, image)
        self.debug("Set token_scope to {}".format(self.token_scope))

    def hostname_has_port(self):
        if len(self.hostname.split(':')) > 1:
            return True
        return False


class RegistryInspectError(Exception):
    pass


class RegistryAuthError(Exception):
    pass


class RegistryInspect():

    def __init__(self, registry=None, repo=None, image=None, tag=None, orig_input=None, debug=False):
        self.debug = debug
        self.registries = util.get_registries()
        self.registry = registry
        self.repo = repo
        self.image = image
        self.tag = tag
        self.orig_input = orig_input
        if self.debug:
            util.output_json(self.registries)
        self.rc = RegistryConnection(debug=self.debug)
        self._setup_rc()

    def _setup_rc(self):
        if self.registry:
            try:
                self.rc.hostname = (x['hostname'] for x in self.registries if x['name'] == self.registry).__next__()
                self.rc.verify = (x['secure'] for x in self.registries if x['name'] == self.registry).__next__()
            except AttributeError:
                self.rc.hostname = (x['hostname'] for x in self.registries if x['name'] == self.registry).next()  # pylint: disable=next-method-called
                self.rc.verify = (x['secure'] for x in self.registries if x['name'] == self.registry).next()  # pylint: disable=next-method-called
            self.rc.registry = self.registry
            self.rc.needs_auth = False

    def inspect(self):
        def _get_inspect_info():

            if self.rc.schema_version == 1:
                return self.rc.inspect_schema1(self.assemble_fqdn(include_tag=False), self.tag)
            else:
                return self.rc.inspect_schema2(self.assemble_fqdn(include_tag=False), self.tag)

        if not self.registry:
            self.find_image_on_registry()
        if not self.rc.pinged:
            self.ping()
        if not self.rc.manifest_json:
            self.get_manifest()
        self.rc.schema_version = self.rc.manifest_json['schemaVersion']
        if self.rc.schema_version == 2:
            self.get_blob_info()
        self.get_tag_list()
        return _get_inspect_info()



    def assemble_fqdn(self, include_tag=True):
        fqdn = "{}".format(self.registry)
        fqdn = fqdn if not self.repo else "{}/{}".format(fqdn, self.repo)
        fqdn += "/{}".format(self.image)
        if include_tag:
            fqdn += ":{}".format(self.tag)
        return fqdn



    def find_image_on_registry(self):
        """
        Find the fully qualified image name for given input when
        registry is unknown
        :return: String fqdn
        """
        for i in [x for x in self.registries if x['search']]:
            docker_repo = False
            self.registry = i['name']
            if not self.repo and self.registry == "docker.io":
                docker_repo = True
                self.repo = 'library'
                self.rc = RegistryConnection(debug=self.debug)
            self._setup_rc()
            try:
                util.write_out("Trying {}".format(self.assemble_fqdn(include_tag=True)))
                self.ping()
            except RegistryInspectError as e:
                util.write_out(str(e))
                continue
            except RegistryAuthError:
                pass

            try:
                manifest_json = self.get_manifest()
                self.rc.manifest_json = manifest_json
                fq = self.registry
                if self.repo:
                    fq += "/{}".format(self.repo)
                fq += "/{}:{}".format(self.image, self.tag)
                return fq

            except RegistryAuthError:
                self.rc = RegistryConnection(debug=self.debug)
            except RegistryInspectError:
                self.rc = RegistryConnection(debug=self.debug)
            if docker_repo:
                self.repo = None
        raise RegistryInspectError("Unable to resolve {}".format(self.orig_input))

    def _ping(self, _scheme, port=None):
        """
        :param _scheme: str(http|https_
        :param port: optional port
        :return: 0 for sucess, 1 for SSL failure, 2 for connection error
        """
        # Inject the port if provided
        hostname = self.rc.hostname if not port else "{}:{}".format(self.rc.hostname, port)
        url = '{}://{}/v2/'.format(_scheme, hostname)
        if self.debug:
            util.write_out("URL: {}".format(url))
        try:
            results = self.rc.get(url)
            if results.reason == "Unauthorized" and self.rc.token:
                raise RegistryAuthError("Unable to establish authenticated connection to {}".format(self.registry))
            if results.reason == "Unauthorized":  # Need a token?
                # Auth hasn't been set up; do so now
                self.rc.needs_auth = True
                self.rc.set_token_from_header(results.headers['Www-authenticate'])
                if not self.rc.token_scope and self.rc.token_service:
                    self.rc.set_token_scope(self.repo, self.image)
                return 3
        except requests.exceptions.SSLError as e:
            if self.debug:
                util.write_out(str(e))
            return 1
        except requests.exceptions.ConnectionError as e:
            if self.debug:
                util.write_out(str(e))
            return 2
        try:
            # Sometimes you get a result from an actual page. A ping response
            # should be an empty dict
            if bool(results.json()):
                return 4
        except ValueError:
            return 4

        if self.rc.hostname != hostname:
            self.rc.port = 5000
        return 0

    def ping(self):
        def _set_auth():
            # If the reg needs auth, attempt again with creds
            self.rc.scheme = scheme
            self.rc.pinged = True
            if self.rc.needs_auth:
                self._ping(scheme)

        scheme = 'https'
        rc = self._ping(scheme)
        if rc == 0:
            return _set_auth()
        if rc in [2, 4] and not self.rc.hostname_has_port():
            if self._ping(scheme, port=5000) == 0:
                return _set_auth()
        else:
            # Now do http
            scheme = 'http'
            rc = self._ping(scheme)
            if rc == 0:
                return _set_auth()
            if rc in [2, 4] and not self.rc.hostname_has_port():
                if self._ping(scheme, port=5000) == 0:
                    return _set_auth()
        raise RegistryInspectError("Unable to connect to registry '{}'".format(self.rc.registry))

    def _assemble_hostname(self):
        return self.rc.hostname if not self.rc.port else "{}:{}".format(self.rc.hostname, self.rc.port)

    def get_manifest(self):
        if self.rc.manifest_json:
            return self.rc.manifest_json

        url = '{}://{}/v2/{}/manifests/{}'.format(self.rc.scheme, self._assemble_hostname(),
                                                  os.path.join(*[x for x in [self.repo, self.image] if x]), self.tag)
        results = self.rc.get(url)
        if results.status_code == 200:
            self.rc.manifest_json = results.json()
            self.rc.orig_manifest = results.content.decode('utf-8')
            return self.rc.manifest_json
        else:
            raise RegistryInspectError("Unable to obtain manifest for "
                                       "{}/{}/{}:{}".format(self.registry, self.repo, self.image, self.tag))

    def get_blob_info(self):
        def _get_digest_from_json():
            if self.rc.manifest_json and self.rc.manifest_json.get('config', None):
                digest = self.rc.manifest_json.get('config').get('digest', None)
                if digest:
                    return digest
            raise RegistryInspectError("You must instantiate the image's manifest date to obtain its digest")

        url = '{}://{}/v2/{}/{}/blobs/{}'.format(self.rc.scheme,
                                                 self._assemble_hostname(),
                                                 self.repo,
                                                 self.image,
                                                 _get_digest_from_json())
        results = self.rc.get(url)
        if results.status_code == 200:
            self.rc.whatever_json = results.json()
            return self.rc.whatever_json
        else:
            raise RegistryInspectError("Unable to obtain blob for "
                                       "{}/{}/{}:{}".format(self.registry, self.repo, self.image, self.tag))

    def get_tag_list(self):
        url = '{}://{}/v2/{}/{}/tags/list'.format(self.rc.scheme, self._assemble_hostname(), self.repo, self.image)
        results = self.rc.get(url)
        if results.status_code == 200:
            self.rc.tag_json = results.json()
            return self.rc.tag_json
        else:
            raise RegistryInspectError("Unable to obtain tag information for "
                                       "{}/{}/{}:{}".format(self.registry, self.repo, self.image, self.tag))

