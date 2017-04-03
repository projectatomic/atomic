import os
import sys
import json
import pipes
from .client import AtomicDocker
from .syscontainers import SystemContainers

import requests

from . import util
import re
from Atomic.backends._docker_errors import NoDockerDaemon, DockerObjectNotFound
from docker.errors import NotFound
from .discovery import RegistryInspect, RegistryInspectError

def find_repo_tag(d, Id, image_name):
    def image_in_repotags(image_name, repotags):
        if image_name in repotags:
            return image_name
        for repotag in repotags:
            if repotag.startswith("{}:".format(image_name)):
                return image_name
        return None

    if not find_repo_tag.images:
        find_repo_tag.images = d.images()
    for image in find_repo_tag.images:
        repo_tag = image_in_repotags(image_name, image['RepoTags'])
        if repo_tag is not None:
            return repo_tag
        if Id == image["Id"]:
            return image["RepoTags"][0]
    return ""
find_repo_tag.images = None

class Atomic(object):
    results = '/var/lib/atomic'
    skull = (u"\u2620").encode('utf-8')

    def __init__(self):
        self.d = AtomicDocker()
        self.args = None
        self.command = None
        self.name = None
        self.image = None
        self.spc = False
        self.system = False
        self.setvalues = None
        self.inspect = None
        self.backend = None
        self.user = None
        self.force = False
        self._images = []
        self.containers = False
        self.images_cache = []
        self.images_all_cache = []
        self.active_containers = []
        self.docker_cmd = None
        self.debug = False
        self.is_python2 = (int(sys.version[0])) < 3
        self.useTTY = True
        self.syscontainers = SystemContainers()
        self.run_opts = None
        self.atomic_config = util.get_atomic_config()
        self.local_tokens = {}
        util.set_proxy()

    def __enter__(self):
        return self

    def __exit__(self, typ, value, traceback):
        try:
            self.d.close()
        except NoDockerDaemon:
            pass

    def docker_binary(self):
        if not self.docker_cmd:
            self.docker_cmd = util.default_docker()
        return self.docker_cmd

    def get_label(self, label, image=None):
        inspect = self._inspect_image(image)
        cfg = inspect.get("Config", None)
        if cfg:
            labels = cfg.get("Labels", [])
            if labels and label in labels:
                return labels[label]
        return ""

    def force_delete_containers(self):
        if self._inspect_image():
            image = self.image
            if self.image.find(":") == -1:
                image += ":latest"
            for c in self.get_containers():
                if c["Image"] == image:
                    self.d.remove_container(c["Id"], force=True)

    def pull(self):
        prevstatus = ""
        for line in self.d.pull(self.image, stream=True):
            bar = json.loads(line)
            status = bar['status']
            if prevstatus != status:
                util.write_out(status, "")
            if 'id' not in bar:
                continue
            if status == "Downloading":
                util.write_out(bar['progress'] + " ")
            elif status == "Extracting":
                util.write_out("Extracting: " + bar['id'])
            elif status == "Pull complete":
                pass
            elif status.startswith("Pulling"):
                util.write_out("Pulling: " + bar['id'])

            prevstatus = status
        util.write_out("")

    def set_args(self, args):
        self.args = args
        try:
            self.image = args.image
        except (NameError, AttributeError):
            pass
        try:
            self.command = args.command
        except (NameError, AttributeError):
            pass

        try:
            self.spc = args.spc
        except (NameError, AttributeError):
            pass

        try:
            self.system = args.system
        except (NameError, AttributeError):
            pass

        try:
            self.name = args.name
        except (NameError, AttributeError):
            pass

        try:
            self.force = args.force
        except (NameError, AttributeError):
            pass

        try:
            self.user = args.user
        except (NameError, AttributeError):
            pass

        if not self.name and self.image is not None:
            self.name = self.image.split("/")[-1].split(":")[0]
            if self.spc:
                self.name = self.name + "-spc"
            if self.system or self.user:
                self.name = self.syscontainers.get_default_system_name(self.image)

        try:
            if not self.name and args.container:
                self.name = args.container
        except (NameError, AttributeError):
            pass

        self.syscontainers.set_args(self.args)

    def _getconfig(self, key, default=None):
        assert self.inspect is not None
        cfg = self.inspect.get("Config")
        if cfg is None:
            return default
        val = cfg.get(key, default)
        if val is None:
            return default
        return val

    def _get_cmd(self):
        return self._getconfig("Cmd", ["/bin/sh"])

    def _get_labels(self):
        return self._getconfig("Labels", [])

    def _inspect_image(self, image=None):
        image = image or self.image
        try:
            if self.syscontainers.has_image(image):
                return self.syscontainers.inspect_system_image(image)
            return self.d.inspect_image(image)
        except (NotFound, requests.exceptions.ConnectionError):
            pass
        return None

    def _inspect_container(self, name=None):
        if name is None:
            name = self.name
        try:
            return self.d.inspect_container(name)
        except (NotFound, requests.exceptions.ConnectionError):
            pass
        return None

    def _get_args(self, label):
        labels = self._get_labels()
        for l in [label, label.lower(), label.capitalize(), label.upper()]:
            if l in labels:
                return labels[l].split()
        return None

    #def ps -> Atomic/ps.py

    #def run -> Atomic/run.py

    def quote(self, args):
        return list(map(pipes.quote, args))

    def cmd_env(self):
        newenv = dict(os.environ)
        newenv['NAME'] = self.name or ""
        newenv['IMAGE'] = self.image or ""

        if hasattr(self.args, 'opt1') and self.args.opt1:
            newenv['OPT1'] = os.path.expandvars(self.args.opt1)

        if hasattr(self.args, 'opt2') and self.args.opt2:
            newenv['OPT2'] = os.path.expandvars(self.args.opt2)

        if hasattr(self.args, 'opt3') and self.args.opt3:
            newenv['OPT3'] = os.path.expandvars(self.args.opt3)

        if not hasattr(self.args, 'PWD'):
            newenv['PWD'] = os.getcwd()

        default_uid = "0"
        with open("/proc/self/loginuid") as f:
            val = f.readline()
            if int(val) <= 2147483647:
                default_uid = val

        if "SUDO_UID" not in newenv:
            newenv["SUDO_UID"] = default_uid

        if 'SUDO_GID' not in newenv:
            newenv["SUDO_GID"] = default_uid

        if self.run_opts is not None:
            newenv["RUN_OPTS"] = self.run_opts
        return newenv

    def gen_cmd(self, cargs):
        args = []
        for c in cargs:
            if c == "IMAGE":
                args.append(self.image)
                continue
            if c == "IMAGE=IMAGE":
                args.append("IMAGE=%s" % self.image)
                continue
            if c == "NAME=NAME":
                args.append("NAME=%s" % self.name)
                continue
            if c == "NAME":
                args.append(self.name)
                continue
            args.append(c)
        if self.is_python2:
            return " ".join([x.decode('utf-8') for x in args])
        else:
            return " ".join(args)

    def get_fq_name(self, image_info):
        if not image_info['RepoTags']:
            return None

        if len(image_info['RepoTags']) > 1:
            if self.image in image_info['RepoTags']:
                return self.image

            possibles = []
            for i in image_info['RepoTags']:
                try:
                    possibles.append(self.get_fq_image_name(i))
                except RegistryInspectError:
                    possibles.append(None)

            if all(x==possibles[0] for x in possibles):
                return possibles[0]

            raise ValueError("\n{} is tagged with multiple repositories. "
                             "Try adding a tag to your input.\n".format(self.image))

        return image_info['RepoTags'][0]

    def is_iid(self):
        for i in self.get_images():
            if i['Id'].startswith(self.image):
                return True
        return False

    def _no_such_image(self):
        raise ValueError("Could not find any image matching '{}'"
                         .format(self.args.image))

    def is_dangling(self, image):
        if image == "<none>":
            return True
        return False

    def _container_exists(self, name):
        try:
            return self.syscontainers.get_checkout(name) or self._inspect_container(name)
        except ValueError:
            return None

    def help(self):
        if os.path.exists("/usr/bin/rpm-ostree"):
            return _('Atomic Management Tool')
        else:
            return _('Atomic Container Tool')

    def _get_layer(self, image):
        def get_label(label):
            return self.get_label(label, image["Id"])
        image = self._inspect_image(image)
        if not image:
            raise ValueError("Image '%s' does not exist" % self.image)
        version = ("%s-%s-%s" % (get_label("Name"), get_label("Version"),
                                 get_label("Release"))).strip("-")
        if 'Parent' in image:
            parent = image['Parent']
        else:
            parent = ""
        return({"Id": image['Id'], "Name": get_label("Name"),
                "Version": version, "RepoTags": image['RepoTags'],
                "Parent": parent})

    def get_layers(self):
        layers = []
        layer = self._get_layer(self.image)
        layers.append(layer)
        while layer["Parent"] != "":
            layer = self._get_layer(layer["Parent"])
            layers.append(layer)
        return layers

    def display(self, cmd):
        util.write_out(cmd)

    def sub_env_strings(self, in_string):
        """
        Performs substitutions on an input string based on defined
        environment variables.
        :param in_string: string to perform the subs on
        :return: string
        """
        # Perform variable subs
        in_string = util.expandvars(in_string, environ=self.cmd_env())

        # Replace undefined variables with blank
        in_string = re.sub(r'\$\{?\S*\}?', '', in_string)

        # Solve whitespacing
        in_string = " ".join(in_string.split())

        return in_string

    def ping(self):
        '''
        Check if the docker daemon is running; if not, exit with
        message and return code 1
        '''
        try:
            self.d.ping()
        except requests.exceptions.ConnectionError:
            raise NoDockerDaemon()

    def _is_container(self, identifier, active=False):
        '''
        Checks is the identifier is a container ID or container name.  If
        it is, returns the full container ID. Else it will return an
        AtomicError.  Takes optional keyword active, which signifies
        that you want to only deal with active containers.
        '''
        if active:
            active_cons = self.get_active_containers()
            active_con_ids = [x['Id'] for x in active_cons]
            cons = active_cons
        else:
            cons = self.get_containers()

        # First check if the container exists by whatever
        # identifier was given
        self.inspect = self._inspect_container(name=identifier)
        if self.inspect is not None:
            # Inspect found a match
            if not active:
                return self.inspect['Id']
            else:
                # Check if the container is active
                if self.inspect['Id'] in active_con_ids:
                    return self.inspect['Id']

        err_append = "Refine your search to narrow results."

        # The identifier might be a partial name?
        con_ids = []
        for con in cons:
            for name in con['Names']:
                if name.startswith("/{0}".format(identifier)):
                    con_ids.append(con['Id'])
                    break

        # More than one match was found
        if len(con_ids) > 1:
            raise AtomicError("Multiple matches were found for {0}. {1}"
                              .format(identifier, err_append))
        # No matches were found
        elif len(con_ids) < 1:
            active_err = '' if not active else 'active '
            error_msg = "Unable to find {0}container '{1}'".format(active_err,
                                                                   identifier)
            raise AtomicError(error_msg)
        else:
            self.inspect = self._inspect_container(con_ids[0])
            return con_ids[0]

    def _is_image(self, identifier):
        '''
        Checks is the identifier is a image ID or a matches an image name.
        If it finds a match, it returns the full image ID. Else it will
        return an AtomicError.
        '''
        err_append = "Refine your search to narrow results."
        image_info = self.get_images()

        inspect = self._inspect_image(image=identifier)
        if inspect is not None:
            self.inspect = inspect
            return inspect['Id']

        name_search = util.image_by_name(identifier, images=image_info)
        if len(name_search) > 0:
            if len(name_search) > 1:
                tmp_image = dict((x['Id'], x['RepoTags']) for x in image_info)
                repo_tags = []
                for name in name_search:
                    for repo_tag in tmp_image.get(name['Id']):
                        if repo_tag.find(identifier) > -1:
                            repo_tags.append(repo_tag)
                raise ValueError("Found more than one image possibly "
                                 "matching '{0}'. They are:\n    {1} \n{2}"
                                 .format(identifier, "\n    ".join(repo_tags),
                                         err_append))
            return name_search[0]['Id']
        # No dice
        raise AtomicError

    def is_duplicate_image(self, image):
        try:
            if self.syscontainers.has_image(image) and self.d.inspect_image(image):
                return True

            return False
        except (NotFound, requests.exceptions.ConnectionError):
            pass
        return False

    def get_input_id(self, identifier):
        '''
        Determine if the input "identifier" is valid.  Return the container or
        image ID when true and raise a ValueError when not
        '''
        try:
            return self._is_image(identifier)
        except AtomicError:
            pass
        try:
            return self._is_container(identifier)
        except AtomicError:
            pass

        if self.syscontainers.has_image(identifier):
            return identifier

        if self.syscontainers.get_checkout(identifier):
            return identifier

        raise DockerObjectNotFound(identifier)

    def _get_docker_images(self, get_all=False):
        try:
            images = self.d.images(all=get_all)
            for i in images:
                i["ImageType"] = "Docker"
                i["ImageId"] = i["Id"]
        except requests.exceptions.ConnectionError:
            raise NoDockerDaemon()
        return images

    def get_images(self, get_all=False):
        '''
        Wrapper function that should be used instead of querying docker
        multiple times for a list of images.
        '''
        if get_all:
            if len(self.images_all_cache) == 0:
                self.images_all_cache = self._get_docker_images(get_all=True) + self.syscontainers.get_system_images(get_all=True)
            return self.images_all_cache
        else:
            if len(self.images_cache) == 0:
                self.images_cache = self._get_docker_images() + self.syscontainers.get_system_images()
            return self.images_cache

    def get_containers(self):
        '''
        Wrapper function that should be used instead of querying docker
        multiple times for a list of containers
        '''
        if not self.containers:
            self.containers = self.d.containers(all=True)

        return self.containers + self.syscontainers.get_containers()

    def get_active_containers(self, refresh=False):
        '''
        Wrapper function for obtaining active containers.  Should be used
        instead of direct queries to docker
        '''
        if len(self.active_containers) == 0 or refresh:
            self.active_containers = self.d.containers(all=False)

        return self.active_containers

    def set_debug(self):
        if self.args.debug:
            self.debug = True

    def get_all_vulnerable_info(self):
        """
        Read and parse the /var/lib/atomic/scan_summary.json object.
        """
        try:
            return json.loads(open(os.path.join(self.results, "scan_summary.json"), "r").read())
        except (IOError, ValueError):
            return {}


    def get_vulnerable_ids(self):
        """
        Reads in /var/lib/atomic/scan_summary.json and returns a list of all
        the uuids that are vulnerable
        :return:
        """
        try:
            summary_results = json.loads(open(os.path.join(self.results, "scan_summary.json"), "r").read())
            vuln_ids = []

            for uuid in summary_results.keys():
                if 'Vulnerable' in summary_results[uuid]:
                    if summary_results[uuid]['Vulnerable']:
                        vuln_ids.append(uuid)
            return vuln_ids
        except IOError:
            return []

    def get_local_tokens(self):
        if len(self.local_tokens) == 0:
            self.local_tokens = self.load_local_tokens()
        return self.local_tokens

    @staticmethod
    def load_local_tokens():
        tokens = {}
        token_file_name = os.path.expanduser('~/.docker/config.json')
        if not os.path.exists(token_file_name):
            return {}
        with open(token_file_name) as token_file:
            token_data = json.load(token_file)
        try:
            for registry in token_data['auths']:
                reg_key = registry
                if registry == 'https://index.docker.io/v1/':
                    reg_key = 'docker.io'
                tokens[reg_key] = token_data['auths'][registry]['auth']
        except KeyError:
            # Just return a blank dict
            pass
        return tokens

    def get_fq_image_name(self, input_image):
        registry, repo, image, tag, digest = util.Decompose(input_image).all
        if not image:
            raise ValueError('Error parsing input: "{}" invalid'.format(input_image))
        if all([True if x else False for x in [registry, image, tag]]):
            img = registry
            if repo:
                img += "/{}".format(repo)
            img += "/{}:{}".format(image, tag)
            return img
        if not registry:
            ri = RegistryInspect(registry, repo, image, tag, digest=digest, debug=self.args.debug, orig_input=self.image)
            return ri.find_image_on_registry()


class AtomicError(Exception):
    pass

