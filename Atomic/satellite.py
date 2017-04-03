import os
import json
try:
    import ConfigParser as configparser
except ImportError:  # py3 compat
    import configparser # pylint: disable=import-error

import requests

from . import util


util.urllib3_disable_warnings()


def push_image_to_satellite(image, server_url, username, password,
                            verify_ssl, docker_client, activation_key,
                            repo_id, debug=False):
    if not image:
        raise ValueError("Image required")
    parts = image.split("/")
    if parts > 1:
        if parts[0].find(".") != -1:
            server_url = parts[0]
            image = ("/").join(parts[1:])
    if not server_url:
        raise ValueError("Satellite server url required")

    if not server_url.startswith("http"):
        server_url = "https://" + server_url

    try:
        sat = SatelliteServer(server_url=server_url, username=username,
                              password=password, verify_ssl=verify_ssl,
                              docker_client=docker_client, debug=debug)
    except IOError as e:
        raise IOError('Failed to initialize Satellite: {0}'.format(e))
    if not sat.is_repo(repo_id):
        raise IOError("""Invalid Repository ID: {0}.  Please create that repository
and try again, or input a different ID.""".format(repo_id).replace('\n', ' '))
    keyData = sat.get_data(repo_id, activation_key)
    content_view_id = keyData.get("content_view_id")
    try:
        util.write_out('Uploading image "{0}" to server "{1}"'.format(
                      image, server_url))
        sat.upload_docker_image(image, repo_id)
        util.write_out("")
    except IOError as e:
        raise IOError('Failed to upload image: {0}'.format(e))
    sat.publish_view(content_view_id, repo_id)
    print("Push Complete")


class SatelliteServer(object):
    # Interact with Satellite API
    def __init__(self, server_url, username, password, verify_ssl,
                 docker_client, debug=False):
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
        self._debug = debug

    def _call_satellite(self, url, req_type='get', payload=None):
        """This function handles requests to the Satellite Server"""
        proxies = util.get_proxy()
        if req_type == 'get':
            if (self._debug):
                print('Calling Satellite URL "{0}"'.format(url))
            r = requests.get(url, auth=(self._username, self._password),
                             verify=self._verify_ssl, proxies=proxies)
        elif req_type == 'post':
            if (self._debug):
                print('Posting to Satellite URL "{0}"'.format(url))
                if payload:
                    print('Satellite HTTP payload:\n{0}'.format(
                          json.dumps(payload, indent=2)))
            r = requests.post(url, auth=(self._username, self._password),
                              data=json.dumps(payload),
                              verify=self._verify_ssl,
                              proxies=proxies)
        elif req_type == 'post-nodata':
            if (self._debug):
                print('Posting to Satellite URL "{0}". No data sent.'.format(
                    url))
            header = {'Content-Type': 'application/json'}
            r = requests.post(url, auth=(self._username, self._password),
                              headers=header, data=json.dumps(payload),
                              verify=self._verify_ssl,
                              proxies=proxies)
        elif req_type == 'put':
            if self._debug:
                print('Putting to Satellite URL "{0}"'.format(url))
            r = requests.put(url, auth=(self._username, self._password),
                             data=payload, verify=self._verify_ssl,
                             proxies=proxies)
        elif req_type == 'put-jsonHead':
            if self._debug:
                print('Putting with json header to Satellite URL "{0}"'
                      .format(url))
            header = {'Content-Type': 'application/json'}
            r = requests.put(url, auth=(self._username, self._password),
                             headers=header, data=json.dumps(payload),
                             verify=self._verify_ssl, proxies=proxies)
        elif req_type == 'put-multi-part':
            if self._debug:
                print('Multi-Part Putting to Satellite URL "{0}"'.format(url))
            header = {
                'multipart': True,
                'accept': 'application/json;version=2',
                'content-type': 'multipart/form-data'
            }
            r = requests.put(url, auth=(self._username, self._password),
                             headers=header, data=payload,
                             verify=self._verify_ssl,
                             proxies=proxies)
        elif req_type == 'delete':
            if self._debug:
                print('Delete call to Satellite URL "{0}"'.format(url))
            header = {'Content-Type': 'application/json'}
            r = requests.delete(url, auth=(self._username, self._password),
                                headers=header, verify=self._verify_ssl,
                                proxies=proxies)
        else:
            raise IOError('Invalid value of "req_type" parameter: {0}'
                             .format(req_type))
        if self._debug:
            print(r)
        try:
            r_json = r.json()
        except IOError:
            # some requests don't return a json object
            return None

        if ('errors' in r_json):
            util.write_err('Error message from Satellite response:\n{0}'
                             .format(r_json['errors']))
        if 'spawned_tasks' in r_json:
            for task in r_json['spawned_tasks']:
                if self._debug:
                    print('Checking status of spawned task {0}'.format(
                        task['task_id']))
                self._call_satellite('{0}/{1}'.format(self._server_url,
                                                      task['_href']))
        return r_json

    # It looks like, while we can't actually get the activation key
    # from the text on the satellite page, it is in the URL of the
    # page. Same for repo id with repo page.  As in,
    # https://sat6-atomic.refarch.bos.redhat.com/activation_keys/
    # {The activation key number is here}/info
    def get_data(self, repo_id, activation_key):
        url = '{0}/katello/api/repositories/{1}'.format(
            self._server_url, repo_id)
        r_json = self._call_satellite(url)
        keyData = {}
        keyData['org_id'] = r_json.get("organization").get("id")
        keyData['product_id'] = r_json.get("product").get("id")
        url = '{0}/katello/api/activation_keys/{1}'.format(
            self._server_url, activation_key)
        r2_json = self._call_satellite(url)
        keyData['content_view_id'] = r2_json.get("content_view_id")
        if self._debug:
            print("key data is {0}".format(keyData))
        return keyData

    @property
    def status(self):
        """Return Satellite server status"""
        if self._debug:
            print('Verifying Satellite server status')
        return self._call_satellite('{0}/api/v2/status/'.format(
            self._server_url))

    def is_repo(self, repo_id):
        """Return true if repo exists"""
        url = '{0}/katello/api/repositories/{1}'.format(
            self._server_url, repo_id)
        if self._debug:
            print('Verifying satellite repository "{0}"'.format(repo_id))
        r_json = self._call_satellite(url)
        if int(repo_id) == r_json.get('id'):
            if self._debug:
                print("Yes it was a repo")
            return True
        else:
            return False

    def _upload_id(self, repo_id):
        """Get a satellite upload ID"""
        url = '{0}/katello/api/repositories/{1}/content_uploads'.format(
            self._server_url, repo_id)
        r_json = self._call_satellite(url, "post-nodata")
        if 'error' in r_json:
            raise IOError('Unable to get a satellite upload ID')
        return r_json.get('upload_id')

    def upload_docker_image(self, image, repo_id):
        """Upload image to  repository"""
        if self._debug:
            print("Getting an upload id")
        upload_id = self._upload_id(repo_id)
        if self._debug:
            print('Uploading image using ID "{0}"'.format(upload_id))
            print('\nUploading image "{0}"'.format(image))
        self._upload_docker_image(image, repo_id, upload_id)
        self._import_upload(upload_id, repo_id)
        self._delete_upload_id(upload_id, repo_id)

    def _upload_docker_image(self, image, repo_id, upload_id):
        if self._debug:
            print("Beginning to upload the image")
        offset = 0
        image_stream = self._docker_client.get_image(image)
        while True:
            content = image_stream.read(self._chunk_size)
            if not content:
                break
            url = "{0}/katello/api/repositories/{1}/content_uploads/{2}".format(self._server_url, repo_id, upload_id)
            util.write_out(".", "")
            payload = {
                'offset': offset,
                'content': content
            }
            r_json = self._call_satellite(url, "put-multi-part", payload)
            if (r_json is not None):
                if ('errors' in r_json):
                    raise IOError("Unable to upload image.  Error:{0}"
                                    .format(r_json.get("errors")))
            offset += self._chunk_size
        image_stream.close()
        if self._debug:
            print("Finished uploading the image data")

    def _delete_upload_id(self, upload_id, repo_id):
        """Delete upload request ID"""
        delete_url = "{0}/katello/api/repositories/{1}/content_uploads/{2}".format(self._server_url, repo_id, upload_id)
        self._call_satellite(delete_url, "delete")
        if self._debug:
            print("Successful Deletion")

    def _import_upload(self, upload_id, repo_id):
        """Import uploaded content"""
        url = '{0}/katello/api/repositories/{1}/import_uploads'.format(
            self._server_url, repo_id)
        if self._debug:
            print('Importing satellite upload {0} into {1}'.format(
                upload_id, repo_id))
        payload = {
            "upload_ids": [upload_id]
            # may need to make the id into a string.  Unclear.
        }
        r_json = self._call_satellite(url, "put-jsonHead", payload)
        if (r_json is not None):
            if ('errors' in r_json):
                raise IOError('Unable to import satellite content into {0}'
                                .format(repo_id))

    def publish_view(self, content_id, repo_id):
        """Publish satellite repository to satellite web server"""
        url = '{0}/katello/api/content_views/{1}/publish/'.format(
            self._server_url, content_id)
        r_json = self._call_satellite(url, "post-nodata")
        if (r_json is not None):
            if ('errors' in r_json):
                raise IOError('Unable to publish satellite repo "{0}"'
                                .format(repo_id))


class SatelliteConfig(object):
    def __init__(self):
        self.c = configparser.ConfigParser()
        self.config_file = os.path.expanduser("~/.satellite/admin.conf")
        self.c.read(self.config_file)
        self.url = self._get("server", "url")
        self.username = self._get("auth", "username")
        self.password = self._get("auth", "password")
        self.verify_ssl = self._getboolean("server", "verify_ssl")
    # Satellite configuration file [optional]:
    # 1. look in (or create) ~/.satellite/admin.conf
    # configuration contents:
    # [server]
    # host = <satellite-server-hostname.example.com>
    # verify_ssl = false
    #
    # # optional auth section
    # [auth]
    # username: <user>
    # password: <pass>
    def _get(self, section, val):
        try:
            return self.c.get(section, val)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return None
        except IOError as e:
            raise IOError("Satellite Bad Value for {0} in {1}. {2}".format(
                val, self.config_file, e))

    def _getboolean(self, section, val):
        try:
            return self.c.getboolean(section, val)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return True
        except IOError as e:
            raise IOError("Satellite Bad Value for {0} in {1}. {2}".format(
                val, self.config_file, e))

    def config(self):
        return {"url": self.url, "verify_ssl": self.verify_ssl, "username": self.username, "password": self.password}
