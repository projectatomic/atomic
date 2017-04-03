import os
import json
try:
    import ConfigParser as configparser
except ImportError:  # py3 compat
    import configparser # pylint: disable=import-error

import requests

from . import util


util.urllib3_disable_warnings()

def push_image_to_pulp(image, server_url, username, password,
                       verify_ssl, docker_client):
    if not image:
        raise ValueError("Image required")
    parts = image.split("/")
    if parts > 1:
        if parts[0].find(".") != -1:
            server_url = parts[0]
            image = ("/").join(parts[1:])

    repo = image.replace("/", "-")
    if not server_url:
        raise ValueError("Pulp server url required")

    if not server_url.startswith("http"):
        server_url = "https://" + server_url

    try:
        pulp = PulpServer(server_url=server_url, username=username,
                          password=password, verify_ssl=verify_ssl,
                          docker_client=docker_client)
    except Exception as e:
        raise IOError('Failed to initialize Pulp: {0}'.format(e))

    try:
        if not pulp.is_repo(repo):
            pulp.create_repo(image, repo)
    except Exception as e:
        raise IOError('Failed to create repository: {0}'.format(e))

    try:
        util.write_out('Uploading image "{0}" to server "{1}"'.format(
            image, server_url))
        pulp.upload_docker_image(image, repo)
        util.write_out("")
    except Exception as e:
        raise IOError('Failed to upload image: {0}'.format(e))

    pulp.publish_repo(repo)
    pulp.export_repo(repo)


class PulpServer(object):

    # Interact with Pulp API
    def __init__(self, server_url, username, password, verify_ssl,
                 docker_client):
        self._server_url = server_url
        self._username = username
        self._password = password
        self._verify_ssl = verify_ssl
        self._docker_client = docker_client
        self._web_distributor = "docker_web_distributor_name_cli"
        self._export_distributor = "docker_export_distributor_name_cli"
        self._importer = "docker_importer"
        self._export_dir = "/var/www/pub/docker/web/"
        self._unit_type_id = "docker_image"
        self._chunk_size = 1048576  # 1 MB per upload call

    def _call_pulp(self, url, req_type='get', payload=None):
        proxies = util.get_proxy()
        if req_type == 'get':
            r = requests.get(url, auth=(self._username, self._password),
                             verify=self._verify_ssl,
                             proxies=proxies)
        elif req_type == 'post':
            r = requests.post(url, auth=(self._username, self._password),
                              data=json.dumps(payload),
                              verify=self._verify_ssl,
                              proxies=proxies)
        elif req_type == 'put':
            # some calls pass in binary data so we don't log payload data or
            # json encode it here
            r = requests.put(url, auth=(self._username, self._password),
                             data=payload, verify=self._verify_ssl,
                             proxies=proxies)
        elif req_type == 'delete':
            r = requests.delete(url, auth=(self._username, self._password),
                                verify=self._verify_ssl, proxies=proxies)
        else:
            raise ValueError('Invalid value of "req_type" parameter: {0}'
                             ''.format(req_type))
        r_json = r.json()
        # some requests return null
        if not r_json:
            return r_json

        if 'error_message' in r_json:
            util.write_err('Error messages from Pulp response:\n{0}'
                             ''.format(r_json['error_message']))

        if 'spawned_tasks' in r_json:
            for task in r_json['spawned_tasks']:
                self._call_pulp('{0}/{1}'.format(self._server_url,
                                                 task['_href']))
        return r_json

    @property
    def status(self):
        # Return pulp server status
        return self._call_pulp('{0}/pulp/api/v2/status/'
                               ''.format(self._server_url))

    def is_repo(self, repo_id):
        # Return true if repo exists
        url = '{0}/pulp/api/v2/repositories/'.format(self._server_url)
        r_json = self._call_pulp(url)
        return repo_id in [repo['id'] for repo in r_json]

    def create_repo(self, image, repo_id, redirect_url=None):
        # Create pulp docker repository
        print('Creating Repo "{0}"'.format(repo_id))
        if not redirect_url:
            redirect_url = '{0}/pulp/docker/{1}'.format(self._server_url,
                                                        repo_id)
            payload = {
                'id': repo_id,
                'display_name': image,
                'description': 'docker image repository',
                'notes': {
                    '_repo-type': 'docker-repo'
                },
                'importer_type_id': self._importer,
                'importer_config': {},
                'distributors': [{
                    'distributor_type_id': 'docker_distributor_web',
                    'distributor_id': self._web_distributor,
                    'distributor_config': {
                        'repo-registry-id': image},
                    'auto_publish': 'true'},
                                 {
                                     'distributor_type_id': 'docker_distributor_export',
                                     'distributor_id': self._export_distributor,
                                     'repo-registry-id': image,
                                     'docker_publish_directory': self._export_dir,
                                     'auto_publish': 'true',
                                     'distributor_config': {
                                         'redirect-url': redirect_url,
                                         'repo-registry-id': image}
                                 }
                ]
            }
            url = '{0}/pulp/api/v2/repositories/'.format(self._server_url)
        r_json = self._call_pulp(url, "post", payload)
        if 'error_message' in r_json:
            raise Exception('Failed to create repository "{0}"'
                            ''.format(repo_id))

    @property
    def _upload_id(self):
        # Get a pulp upload ID
        url = '{0}/pulp/api/v2/content/uploads/'.format(self._server_url)
        r_json = self._call_pulp(url, "post")
        if 'error_message' in r_json:
            raise Exception('Unable to get a pulp upload ID')
        return r_json['upload_id']

    def _delete_upload_id(self, upload_id):
        # Delete upload request ID
        url = '{0}/pulp/api/v2/content/uploads/{1}/'.format(self._server_url,
                                                            upload_id)
        self._call_pulp(url, "delete")

    def upload_docker_image(self, image, repo_id):
        # Upload image to pulp repository
        upload_id = self._upload_id
        self._upload_docker_image(upload_id, image)
        self._import_upload(upload_id, repo_id)
        self._delete_upload_id(upload_id)

    def _upload_docker_image(self, upload_id, image):
        offset = 0
        image_stream = self._docker_client.get_image(image)
        while True:
            data = image_stream.read(self._chunk_size)
            if not data:
                break
            url = '{0}/pulp/api/v2/content/uploads/{1}/{2}/' \
                  ''.format(self._server_url, upload_id, offset)
            util.write_out(".", "")
            self._call_pulp(url, "put", data)
            offset += self._chunk_size
            image_stream.close()

    def _import_upload(self, upload_id, repo_id):
        # Import uploaded content
        url = '{0}/pulp/api/v2/repositories/{1}/actions/import_upload/' \
              ''.format(self._server_url, repo_id)
        payload = {
            'upload_id': upload_id,
            'unit_type_id': self._unit_type_id,
            'unit_key': None,
            'unit_metadata': None,
            'override_config': None
        }
        r_json = self._call_pulp(url, "post", payload)
        if 'error_message' in r_json:
            raise Exception('Unable to import pulp content into {0}'
                            ''.format(repo_id))

    def publish_repo(self, repo_id):
        # Publish pulp repository to pulp web server
        url = '{0}/pulp/api/v2/repositories/{1}/actions/publish/' \
              ''.format(self._server_url, repo_id)
        payload = {
            "id": self._web_distributor,
            "override_config": {}
        }
        r_json = self._call_pulp(url, "post", payload)
        if 'error_message' in r_json:
            raise Exception('Unable to publish pulp repo "{0}"'
                            ''.format(repo_id))

    def export_repo(self, repo_id):
        # Export pulp repository to pulp web server as tar

        # The tarball is split into the layer components and crane metadata.
        # It is for the purpose of uploading to remote crane server
        url = '{0}/pulp/api/v2/repositories/{1}/actions/publish/' \
              ''.format(self._server_url, repo_id)
        payload = {
            "id": self._export_distributor,
            "override_config": {
                "export_file": '{0}{1}.tar'.format(self._export_dir, repo_id),
            }
        }
        r_json = self._call_pulp(url, "post", payload)
        if 'error_message' in r_json:
            raise Exception('Unable to export pulp repo "{0}"'.format(repo_id))


class PulpConfig(object):
    # pulp configuration:
    # 1. look in ~/.pulp/admin.conf
    # configuration contents:
    # [server]
    #    host = <pulp-server-hostname.example.com>
    #    verify_ssl = false

    # #optional auth section
    # [auth]
    #    username: <user>
    #    password: <pass>
    def __init__(self):
        self.c = configparser.ConfigParser()
        self.config_file = os.path.expanduser("~/.pulp/admin.conf")
        self.c.read(self.config_file)
        self.url = self._get("server", "host")
        self.username = self._get("auth", "username")
        self.password = self._get("auth", "password")
        self.verify_ssl = self._getboolean("server", "verify_ssl")

    def _get(self, section, val):
        try:
            return self.c.get(section, val)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return None
        except ValueError as e:
            raise ValueError("Bad Value for %s in %s. %s" %
                             (val, self.config_file, e))

    def _getboolean(self, section, val):
        try:
            return self.c.getboolean(section, val)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return True
        except ValueError as e:
            raise ValueError("Bad Value for %s in %s. %s" %
                             (val, self.config_file, e))

    def config(self):
        return {"url": self.url, "verify_ssl": self.verify_ssl,
                "username": self.username, "password": self.password}
