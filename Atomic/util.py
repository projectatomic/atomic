import errno
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
from yaml import YAMLError
import tempfile
import shutil
import re
import requests
try:
    from urlparse import urlparse #pylint: disable=import-error
except ImportError:
    from urllib.parse import urlparse #pylint: disable=no-name-in-module,import-error

# Atomic Utility Module

ReturnTuple = collections.namedtuple('ReturnTuple',
                                     ['return_code', 'stdout', 'stderr'])
ATOMIC_CONF = os.environ.get('ATOMIC_CONF', '/etc/atomic.conf')
ATOMIC_CONFD = os.environ.get('ATOMIC_CONFD', '/etc/atomic.d/')
ATOMIC_LIBEXEC = os.environ.get('ATOMIC_LIBEXEC', '/usr/libexec/atomic')
ATOMIC_VAR_LIB = os.environ.get('ATOMIC_VAR_LIB', '/var/lib/atomic')

BWRAP_OCI_PATH = "/usr/bin/bwrap-oci"
RUNC_PATH = "/bin/runc"

def runc_available():
    return os.path.exists(RUNC_PATH)

def bwrap_oci_available():
    return os.path.exists(BWRAP_OCI_PATH)

def check_if_python2():
    if int(sys.version_info[0]) < 3:
        _input = raw_input # pylint: disable=undefined-variable,raw_input-builtin
        return _input, True
    else:
        _input = input
        return _input, False

input, is_python2 = check_if_python2() # pylint: disable=redefined-builtin

def decompose(compound_name):
    # '[reg/]repo[:tag]' -> (reg, repo, tag)
    reg, repo, tag = '', compound_name, ''
    if '/' in repo:
        reg, repo = repo.split('/', 1)
    if ':' in repo:
        repo, tag = repo.rsplit(':', 1)
    return reg, repo, tag

def image_by_name(img_name, images=None):
    # Returns a list of image data for images which match img_name. Will
    # optionally take a list of images from a docker.Client.images
    # query to avoid multiple docker queries.
    i_reg, i_rep, i_tag = decompose(img_name)

    # Correct for bash-style matching expressions.
    if not i_reg:
        i_reg = '*'
    if not i_tag:
        i_tag = '*'

    # If the images were not passed in, go get them.
    if images is None:
        with AtomicDocker() as c:
            images = c.images(all=False)

    valid_images = []
    for i in images:
        if not i["RepoTags"]:
            continue
        for t in i['RepoTags']:
            reg, rep, tag = decompose(t)
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
    # Run a command as a subprocess.
    # Return a triple of return code, standard out, standard err.
    proc = subprocess.Popen(cmd, cwd=cwd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, close_fds=True)
    out, err = proc.communicate()
    return ReturnTuple(proc.returncode, stdout=out, stderr=err)

class FileNotFound(Exception):
    pass

# Wrappers for Python's subprocess which override the default for close_fds,
# since we are a privileged process, and we don't want to leak things like
# the docker socket into child processes by default
def check_call(cmd, env=None, stdin=None, stderr=None, stdout=None):
    if not env:
        env=os.environ
    # Make sure cmd is a list; break if needed
    if not isinstance(cmd, list):
        if is_python2:
            # The command contains a non-ascii character
            cmd = shlex.split(" ".join([x.encode('utf-8') for x in cmd.split()]))
        else:
            cmd = shlex.split(cmd)
    try:
        return subprocess.check_call(cmd, env=env, stdin=stdin, stderr=stderr, stdout=stdout, close_fds=True)
    except OSError as e:
        if e.args[0] == errno.ENOENT:
            raise FileNotFound("Cannot find file: `{}`".format(cmd[0]))
        raise

def check_output(cmd, env=None, stdin=None, stderr=None):
    if not env:
        env=os.environ
    # Make sure cmd is a list
    if not isinstance(cmd, list):
        cmd = shlex.split(cmd)
    try:
        return subprocess.check_output(cmd, env=env, stdin=stdin, stderr=stderr, close_fds=True)
    except OSError as e:
        if e.args[0] == errno.ENOENT:
            raise FileNotFound("Cannot find file: `{}`".format(cmd[0]))
        raise

def call(cmd, env=None, stdin=None, stderr=None, stdout=None):
    if not env:
        env=os.environ
    # Make sure cmd is a list
    if not isinstance(cmd, list):
        cmd = shlex.split(cmd)
    try:
        return subprocess.call(cmd, env=env, stdin=stdin, stderr=stderr, stdout=stdout, close_fds=True)
    except OSError as e:
        if e.args[0] == errno.ENOENT:
            raise FileNotFound("Cannot find file: `{}`".format(cmd[0]))
        raise

def default_container_context():
    if selinux.is_selinux_enabled() != 0:
        with open(selinux.selinux_lxc_contexts_path()) as fd:
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
    _output(sys.stdout, output, lf)


def write_err(output, lf="\n"):
    _output(sys.stderr, output, lf)


def _output(fd, output, lf):
    fd.flush()

    if is_python2:
        if isinstance(output, unicode): #pylint: disable=undefined-variable,unicode-builtin
            output = output.encode('utf-8')
        fd.write(output + lf)
    else:
        fd.write(output + str(lf))

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

def skopeo_inspect(image, args=None):
    if not args:
        args=[]

    # Performs remote inspection of an image on a registry
    # :param image: fully qualified name
    # :param args: additional parameters to pass to Skopeo
    # :return: Returns json formatted data

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


def skopeo_delete(image, args=None):
    """
    Performs remote delete of an image on a registry
    :param image: fully qualified name
    :param args: additional parameters to pass to Skopeo
    :return: True if image marked for deletion
    """
    if not args:
        args=[]

    cmd = ['skopeo', 'delete'] + args + [image]
    try:
        results = subp(cmd)
    except OSError:
        raise ValueError("skopeo must be installed to perform remote operations")
    if results.return_code is not 0:
        # Only v2 registries supported
        check_v1_registry(image)
        raise ValueError("Unable to interact with this registry: {}".format(results.stderr))
    else:
        return True

def skopeo_layers(image, args=None, layers=None):
    """
    Fetch image layers through Skopeo
    :param image: fully qualified name
    :param args: additional parameters to pass to Skopeo
    :param layers: if set, specify what layers must be downloaded
    :return: Returns the temporary directory with the layers
    """
    if not args:
        args=[]
    if not layers:
        layers=[]
    success = False
    temp_dir = tempfile.mkdtemp()
    try:
        args = ['skopeo', 'layers'] + args + [image] + layers
        r = subp(args, cwd=temp_dir)
        if r.return_code != 0:
            check_v1_registry(image)
            raise ValueError("Unable to interact with this registry: {}".format(r.stderr))
        success = True
    except OSError:
        raise ValueError("skopeo must be installed to perform remote inspections")
    finally:
        if not success:
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
        super(NoDockerDaemon, self).__init__("The docker daemon does not appear to be running.")


class DockerObjectNotFound(ValueError):
    def __init__(self, msg):
        super(DockerObjectNotFound, self).__init__("Unable to associate '{}' with an image or container".format(msg))

def get_atomic_config():
    # Returns the atomic configuration file (/etc/atomic.conf)
    # in a dict
    # :return: dict based structure of the atomic config file
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
            try:
                temp_conf = yaml_load(conf_file)
            except YAMLError:
                write_err("Error: Unable to load scannerfile %s.  Continuing..." %f)
            try:
                if temp_conf.get('type') == "scanner":
                    scanners.append(temp_conf)
            except AttributeError:
                pass
    return scanners

def default_docker():
    if not default_docker.cache:
        atomic_config = get_atomic_config()
        default_docker.cache = atomic_config.get('default_docker','docker')
    return default_docker.cache
default_docker.cache = None

def default_docker_lib():
    if not default_docker_lib.cache:
        default_docker_lib.cache = "/var/lib/%s" % default_docker()
    return default_docker_lib.cache
default_docker_lib.cache = None

# Utilities for dealing with config files that use bourne shell
# syntax, such as /etc/sysconfig/docker-storage-setup

def sh_make_var_pattern(var):
    return '^[ \t]*%s[ \t]*=[ \t]*"(.*)"[ \t]*$' % re.escape(var)

def sh_modify_var_in_text(text, var, modifier, default=""):
    def sub(match):
        return var + '="' + modifier(match.group(1)) + '"'
    (new_text, n_subs) = re.subn(sh_make_var_pattern(var), sub, text, flags=re.MULTILINE)
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

def sh_get_var_in_text(text, var, default=""):
    match = None
    for match in re.finditer(sh_make_var_pattern(var), text, flags=re.MULTILINE):
        pass
    if match:
        return match.group(1)
    else:
        return default

def sh_get_var_in_file(path, var, default=""):
    if os.path.exists(path):
        with open(path, "r") as f:
            return sh_get_var_in_text(f.read(), var, default)
    else:
        return default

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
    try:
        results = client.search(image)
        for x in results:
            if x['name'] == image:
                return '{}/{}'.format(x['registry_name'], x['name'])
    except (ValueError, IOError) as e:
        if e.args[0].args[0] == errno.ENOENT:
            raise ValueError("Image not found")
    return None

def is_user_mode():
    return os.geteuid() != 0

def generate_validation_manifest(img_rootfs=None, img_tar=None, keywords=""):
    """
    Executes the gomtree validation manifest creation command
    :param img_rootfs: path to directory
    :param img_tar: path to tar file (or tgz file)
    :param keywords: use only the keywords specified to create the manifest
    :return: output of gomtree validation manifest creation
    """
    if img_rootfs == None and img_tar == None:
        write_out("no source for gomtree to generate a manifest from")
    if img_rootfs:
        cmd = [ATOMIC_LIBEXEC + '/gomtree','-c','-p',img_rootfs]
    elif img_tar:
        cmd = [ATOMIC_LIBEXEC + '/gomtree','-c','-T',img_tar]
    if keywords:
        cmd += ['-k',keywords]
    return subp(cmd)

def validate_manifest(spec, img_rootfs=None, img_tar=None, keywords=""):
    """
    Executes the gomtree validation manife  st validation command
    :param img_rootfs: path to directory
    :param img_tar: path to tar file (or tgz file)
    :param keywords: use only the keywords specified to validate the manifest
    :return: output of gomtree validation manifest validation
    """
    if img_rootfs == None and img_tar == None:
        write_out("no source for gomtree to validate a manifest")
    if img_rootfs:
        cmd = [ATOMIC_LIBEXEC + '/gomtree', '-p', img_rootfs, '-f', spec]
    elif img_tar:
        cmd = [ATOMIC_LIBEXEC + '/gomtree','-T',img_tar, '-f', spec]
    if keywords:
        cmd += ['-k',keywords]
    return subp(cmd)
