import shlex
import sys
import json
import subprocess
import collections
from fnmatch import fnmatch as matches
import os
import selinux
from .client import AtomicDocker
from yaml import load as yaml_load
import tempfile
import shutil
import re
import requests
try:
    from urlparse import urlparse #pylint: disable=import-error
except:
    from urllib.parse import urlparse #pylint: disable=no-name-in-module,import-error

"""Atomic Utility Module"""

ReturnTuple = collections.namedtuple('ReturnTuple',
                                     ['return_code', 'stdout', 'stderr'])
ATOMIC_CONF = os.environ.get('ATOMIC_CONF', '/etc/atomic.conf')
ATOMIC_CONFD = os.environ.get('ATOMIC_CONFD', '/etc/atomic.d/')
_default_docker=None
_default_docker_lib=None


def check_if_python2():
    if int(sys.version_info[0]) < 3:
        _input = raw_input # pylint: disable=undefined-variable
        return _input, True
    else:
        _input = input
        return _input, False

input, is_python2 = check_if_python2()

def _decompose(compound_name):
    """ '[reg/]repo[:tag]' -> (reg, repo, tag) """
    reg, repo, tag = '', compound_name, ''
    if '/' in repo:
        reg, repo = repo.split('/', 1)
    if ':' in repo:
        repo, tag = repo.rsplit(':', 1)
    return reg, repo, tag

def image_by_name(img_name, images=None):
    """
    Returns a list of image data for images which match img_name. Will
    optionally take a list of images from a docker.Client.images
    query to avoid multiple docker queries.
    """
    i_reg, i_rep, i_tag = _decompose(img_name)

    # Correct for bash-style matching expressions.
    if not i_reg:
        i_reg = '*'
    if not i_tag:
        i_tag = '*'

    # If the images were not passed in, go get them.
    if images is None:
        c = AtomicDocker()
        images = c.images(all=False)

    valid_images = []
    for i in images:
        for t in i['RepoTags']:
            reg, rep, tag = _decompose(t)
            if matches(reg, i_reg) \
                    and matches(rep, i_rep) \
                    and matches(tag, i_tag):
                valid_images.append(i)
                break
            # Some repo after decompose end up with the img_name
            # at the end.  i.e. rhel7/rsyslog
            if rep.endswith(img_name):
                valid_images.append(i)
                break
    return valid_images


def subp(cmd, cwd=None):
    """
    Run a command as a subprocess.
    Return a triple of return code, standard out, standard err.
    """
    proc = subprocess.Popen(cmd, cwd=cwd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, close_fds=True)
    out, err = proc.communicate()
    return ReturnTuple(proc.returncode, stdout=out, stderr=err)

# Wrappers for Python's subprocess which override the default for close_fds,
# since we are a privileged process, and we don't want to leak things like
# the docker socket into child processes by default
def check_call(cmd, env=os.environ, stdin=None, stderr=None, stdout=None):
    # Make sure cmd is a list; break if needed
    if not isinstance(cmd, list):
        if is_python2:
            # The command contains a non-ascii character
            cmd = shlex.split(" ".join([x.encode('utf-8') for x in cmd.split()]))
        else:
            cmd = shlex.split(cmd)
    return subprocess.check_call(cmd, env=env, stdin=stdin, stderr=stderr, stdout=stdout, close_fds=True)

def check_output(cmd, env=os.environ, stdin=None, stderr=None):
    # Make sure cmd is a list
    if not isinstance(cmd, list):
        cmd = shlex.split(cmd)
    return subprocess.check_output(cmd, env=env, stdin=stdin, stderr=stderr, close_fds=True)

def call(cmd, env=os.environ, stdin=None, stderr=None, stdout=None):
    # Make sure cmd is a list
    if not isinstance(cmd, list):
        cmd = shlex.split(cmd)
    return subprocess.call(cmd, env=env, stdin=stdin, stderr=stderr, stdout=stdout, close_fds=True)

def default_container_context():
    if selinux.is_selinux_enabled() != 0:
        fd = open(selinux.selinux_lxc_contexts_path())
        for i in fd.readlines():
            name, context = i.split("=")
            if name.strip() == "file":
                return context.strip("\n\" ")
    return ""

def default_ro_container_context():
    if selinux.is_selinux_enabled() != 0:
        return selinux.getfilecon("/usr")[1]
    return ""

def write_out(output, lf="\n"):
    sys.stdout.flush()
    if is_python2:
        sys.stdout.write(output.encode('utf-8') + lf)
    else:
        sys.stdout.write(output + str(lf))


def output_json(json_data):
    ''' Pretty print json data '''
    write_out(json.dumps(json_data, indent=4, separators=(',', ': ')))


def get_mounts_by_path():
    '''
    Gets all mounted devices and paths
    :return: dict of mounted devices and related information by path
    '''
    mount_info = []
    f = open('/proc/mounts', 'r')
    for line in f:
        _tmp = line.split(" ")
        mount_info.append({'path': _tmp[1],
                           'device': _tmp[0],
                           'type': _tmp[2],
                           'options': _tmp[3]
                           }
                          )
    return mount_info


def is_dock_obj_mounted(docker_obj):
    '''
    Check if the provided docker object, which needs to be an ID,
    is currently mounted and should be considered "busy"
    :param docker_obj: str, must be in ID format
    :return: bool True or False
    '''
    mount_info = get_mounts_by_path()
    devices = [x['device'] for x in mount_info]
    # If we can find the ID of the object in the list
    # of devices which comes from mount, safe to assume
    # it is busy.
    return any(docker_obj in x for x in devices)


def urllib3_disable_warnings():
    if not 'requests' in sys.modules:
        import requests
    else:
        requests = sys.modules['requests']

    # On latest Fedora, this is a symlink
    if hasattr(requests, 'packages'):
        requests.packages.urllib3.disable_warnings() #pylint: disable=maybe-no-member
    else:
        # But with python-requests-2.4.3-1.el7.noarch, we need
        # to talk to urllib3 directly
        have_urllib3 = False
        try:
            if not 'urllib3' in sys.modules:
                import urllib3
                have_urllib3 = True
        except ImportError:
            pass
        if have_urllib3:
            # Except only call disable-warnings if it exists
            if hasattr(urllib3, 'disable_warnings'):
                urllib3.disable_warnings()


def skopeo_inspect(image, args=[]):
    """
    Performs remote inspection of an image on a registry
    :param image: fully qualified name
    :param args: additional parameters to pass to Skopeo
    :return: Returns json formatted data
    """

    cmd = ['skopeo', 'inspect'] + args + [image]
    try:
        results = subp(cmd)
    except OSError:
        raise ValueError("skopeo must be installed to perform remote inspections")
    if results.return_code is not 0:
        # Need to check if we are dealing with a v1 registry
        check_v1_registry(image)
        raise ValueError("Unable to interact with this registry: {}".format(results.stderr))
    else:
        return json.loads(results.stdout.decode('utf-8'))


def skopeo_layers(image, args=[], layers=[]):
    """
    Fetch image layers through Skopeo
    :param image: fully qualified name
    :param args: additional parameters to pass to Skopeo
    :param layers: if set, specify what layers must be downloaded
    :return: Returns the temporary directory with the layers
    """
    temp_dir = tempfile.mkdtemp()
    try:
        args = ['skopeo', 'layers'] + args + [image] + layers
        r = subp(args, cwd=temp_dir)
        if r.return_code != 0:
            check_v1_registry(image)
            raise ValueError("Unable to interact with this registry: {}".format(r.stderr))
    except OSError:
        raise ValueError("skopeo must be installed to perform remote inspections")
    finally:
        shutil.rmtree(temp_dir)

    return temp_dir


def check_v1_registry(image):
    # Skopeo cannot interact with a v1 registry
    netloc = (urlparse(image)).netloc
    v1_url = "https://{}/v1/_ping".format(netloc)
    if requests.get(v1_url).status_code == 200:
        raise ValueError("\nUnable to interact with a V1 registry.")

class NoDockerDaemon(Exception):
    def __init__(self):
        Exception.__init__(self, "The docker daemon does not appear to be running.")


class DockerObjectNotFound(ValueError):
    def __init__(self, msg):
        Exception.__init__(self, "Unable to associate '{}' with an image or container".format(msg))

def get_atomic_config():
    """
    Returns the atomic configuration file (/etc/atomic.conf)
    in a dict
    :return: dict based structure of the atomic config file
    """
    if not os.path.exists(ATOMIC_CONF):
        raise ValueError("{} does not exist".format(ATOMIC_CONF))
    with open(ATOMIC_CONF, 'r') as conf_file:
        return yaml_load(conf_file)

def get_atomic_config_item(config_items, atomic_config=None):
    """
    Lookup and return the atomic configuration file value
    for a given structure. Returns None if the option
    cannot be found.
    """
    def _recursive_get(atomic_config, items):
        yaml_struct = atomic_config
        try:
            for i in items:
                yaml_struct = yaml_struct[i]
        except KeyError:
            return None
        return yaml_struct
    if atomic_config is None:
        atomic_config = get_atomic_config()
    return _recursive_get(atomic_config, config_items)

def get_scanners():
    scanners = []
    if not os.path.exists(ATOMIC_CONFD):
        raise ValueError("{} does not exist".format(ATOMIC_CONFD))
    files = [os.path.join(ATOMIC_CONFD, x) for x in os.listdir(ATOMIC_CONFD) if os.path.isfile(os.path.join(ATOMIC_CONFD, x))]
    for f in files:
        with open(f, 'r') as conf_file:
            temp_conf = yaml_load(conf_file)
            try:
                if temp_conf.get('type') == "scanner":
                    scanners.append(temp_conf)
            except AttributeError:
                pass
    return scanners

def default_docker():
    global _default_docker
    if not _default_docker:
        atomic_config = get_atomic_config()
        _default_docker = atomic_config.get('default_docker','docker')
    return _default_docker

def default_docker_lib():
    global _default_docker_lib
    if not _default_docker_lib:
        _default_docker_lib = "/var/lib/%s" % default_docker()
    return _default_docker_lib

# Utilities for dealing with config files that use bourne shell
# syntax, such as /etc/sysconfig/docker-storage-setup

def sh_modify_var_in_text(text, var, modifier, default=""):
    pattern = '^[ \t]*%s[ \t]*=[ \t]*"(.*)"[ \t]*$' % re.escape(var)
    def sub(match):
        return var + '="' + modifier(match.group(1)) + '"'
    (new_text, n_subs) = re.subn(pattern, sub, text, flags=re.MULTILINE)
    if n_subs != 0:
        return new_text
    else:
        return text + '\n' + var + '="' + modifier(default) + '"\n'

def sh_modify_var_in_file(path, var, modifier, default=""):
    if os.path.exists(path):
        with open(path, "r") as f:
            text = f.read()
    else:
        text = ""
    with open(path, "w") as f:
        f.write(sh_modify_var_in_text(text, var, modifier, default))

def sh_set_add(a, b):
    return " ".join(list(set(a.split()) | set(b)))

def sh_set_del(a, b):
    return " ".join(list(set(a.split()) - set(b)))

def find_remote_image(client, image):
    """
    Based on the user's input, see if we can associate the input with a remote
    registry and image.
    :return: str(fq name)
    """
    results = client.search(image)
    for x in results:
        if x['name'] == image:
            return '{}/{}'.format(x['registry_name'], x['name'])
    return None
