import argparse
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
from yaml import safe_load
from yaml import YAMLError
from yaml.scanner import ScannerError
import tempfile
import shutil
import re
import requests

# Atomic Utility Module

ReturnTuple = collections.namedtuple('ReturnTuple',
                                     ['return_code', 'stdout', 'stderr'])
ATOMIC_CONF = os.environ.get('ATOMIC_CONF', '/etc/atomic.conf')
ATOMIC_CONFD = os.environ.get('ATOMIC_CONFD', '/etc/atomic.d/')
ATOMIC_LIBEXEC = os.environ.get('ATOMIC_LIBEXEC', '/usr/libexec/atomic')
ATOMIC_VAR_LIB = os.environ.get('ATOMIC_VAR_LIB', '/var/lib/atomic')

GOMTREE_PATH = "/usr/bin/gomtree"
BWRAP_OCI_PATH = "/usr/bin/bwrap-oci"
RUNC_PATH = "/bin/runc"


def gomtree_available():
    return os.path.exists(GOMTREE_PATH)

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
    # TODO: this doesn't behave when the registry is omitted or using hub "library" images
    #       we should really decompose into reg, repo, image and tag components
    # 'reg/repo/image[:tag]' -> (reg, repo, image, tag)
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


def subp(cmd, cwd=None, newline=False):
    # Run a command as a subprocess.
    # Return a triple of return code, standard out, standard err.
    proc = subprocess.Popen(cmd, cwd=cwd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, close_fds=True,
                            universal_newlines=newline)
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

def skopeo_inspect(image, args=None, return_json=True, newline=False, quiet=False):
    if not args:
        args=[]

    # Performs remote inspection of an image on a registry
    # :param image: fully qualified name
    # :param args: additional parameters to pass to Skopeo
    # :param fail_silent: return false if failed
    # :return: Returns json formatted data or false

    # Adding in --verify-tls=false to deal with the change in skopeo
    # policy. The prior inspections were also false.  We need to define
    # a way to determine if the registry is insecure according to the
    # docker configuration. If so, then use false in the future.  This
    # is complicated by the fact that CIDR notation can be used in the
    # docker conf
    cmd = ['skopeo', '--tls-verify=false', 'inspect'] + args + [image]
    try:
        results = subp(cmd, newline=newline)
    except OSError:
        raise ValueError("skopeo must be installed to perform remote inspections")
    if results.return_code is not 0:
        if quiet:
            return False
        raise ValueError(results)
    else:
        if return_json:
            return json.loads(results.stdout.decode('utf-8'))
        else:
            return results.stdout


def skopeo_delete(image, args=None):
    """
    Performs remote delete of an image on a registry
    :param image: fully qualified name
    :param args: additional parameters to pass to Skopeo
    :return: True if image marked for deletion
    """
    if not args:
        args=[]

    cmd = ['skopeo', 'tls-verify=false', 'delete'] + args + [image]
    try:
        results = subp(cmd)
    except OSError:
        raise ValueError("skopeo must be installed to perform remote operations")
    if results.return_code is not 0:
        raise ValueError(results)
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
        args = ['skopeo', '--tls-verify=false', 'layers'] + args + [image] + layers
        r = subp(args, cwd=temp_dir)
        if r.return_code != 0:
            raise ValueError(r)
        success = True
    except OSError:
        raise ValueError("skopeo must be installed to perform remote inspections")
    finally:
        if not success:
            shutil.rmtree(temp_dir)
    return temp_dir

def skopeo_standalone_sign(image, manifest_file_name, fingerprint, signature_path, debug=False):
    cmd = ['skopeo']
    if debug:
        cmd = cmd + ['--debug']
    cmd = cmd + ['standalone-sign', manifest_file_name, image,
                 fingerprint, "-o", signature_path]
    return check_call(cmd)

def skopeo_manifest_digest(manifest_file, debug=False):
    cmd = ['skopeo']
    if debug:
        cmd = cmd + ['--debug']
    cmd = cmd  + ['manifest-digest', manifest_file]
    return check_output(cmd).rstrip().decode()

def skopeo_copy(source, destination, debug=False):
    cmd = ['skopeo']
    if debug:
        cmd = cmd + ['--debug']
    cmd = cmd + ['copy']
    if destination.startswith("docker-daemon"):
        cmd = cmd + ['--remove-signatures']
    cmd = cmd + [source, destination]
    return check_call(cmd)

class NoDockerDaemon(Exception):
    def __init__(self):
        super(NoDockerDaemon, self).__init__("The docker daemon does not appear to be running.")


class DockerObjectNotFound(ValueError):
    def __init__(self, msg):
        super(DockerObjectNotFound, self).__init__("Unable to associate '{}' with an image or container".format(msg))

def get_atomic_config(atomic_config=None):
    """
    Get the atomic configuration file (/etc/atomic.conf) as a dict
    :param atomic_conf: path to override atomic.conf, primarily for testing
    :return: dict based structure of the atomic config file
    """
    if not atomic_config:
        atomic_config = ATOMIC_CONF
    if not os.path.exists(atomic_config):
        raise ValueError("{} does not exist".format(atomic_config))
    with open(atomic_config, 'r') as conf_file:
        return yaml_load(conf_file)

def write_registry_config(scope):
    """
    Write registry sigstore configuration file
    :param scope: registry string
    :return: True on success
    """
    # FIXME: pending agreement on registry sigstore layout
    registry_dir = get_atomic_config_item(['registry_sigstore_dir'], get_atomic_config())
    write_out("TODO: Writing trust config for %s to %s" % (scope, registry_dir))
    return False

def install_pubkey(key_name, key_url):
    """
    Installs public key to system config directory
    :param key_name: id of key used as filename
    :param key_url: download URI of public key
    :return: pubkey path string or False
    """
    pubkeys_dir = get_atomic_config_item(['pubkeys_dir'], get_atomic_config())
    pubkey_file = "%s/%s" % (pubkeys_dir, key_name)
    if not os.path.exists(pubkeys_dir):
        os.mkdir(pubkeys_dir)
    if os.path.exists(pubkey_file):
        write_out("Public key %s already installed at %s" % (key_name, pubkey_file))
    else:
        r = requests.get(key_url)
        if r.status_code == 200:
            with open(pubkey_file, 'w') as pubfile:
                pubfile.write(r.content)
            write_out("Installed public key %s" % pubkey_file)
        else:
            write_out("WARNING: Could not download public key using URL %s." % key_url)
            write_out("Download the public key manually and install as %s" % pubkey_file)
    return pubkey_file

def update_trust_policy(trust_scope, pubkey_path, sigstore_url):
    """
    Add trust policy for the specified registry scope
    :param trust_scope: registry/repository scope
    :param pubkey_path: absolute public key path
    :param sigstore_url: url of sigstore
    :return: True if success
    """
    # FIXME: pending feedback on manage policy
    write_out("TODO: Adding trust policy: %s %s %s" % (trust_scope, pubkey_path, sigstore_url))
    return False

def add_opt(sub):
    sub.add_argument("--opt1", dest="opt1",help=argparse.SUPPRESS)
    sub.add_argument("--opt2", dest="opt2",help=argparse.SUPPRESS)
    sub.add_argument("--opt3", dest="opt3",help=argparse.SUPPRESS)

def get_atomic_config_item(config_items, atomic_config=None):
    """
    Lookup and return the atomic configuration file value
    for a given structure. Returns None if the option
    cannot be found.

    ** config_items must be a list!
    """

    assert isinstance(config_items, list)

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
                if temp_conf.get('type') == "scanner":
                    scanners.append(temp_conf)
            except YAMLError:
                write_err("Error: Unable to load scannerfile %s.  Continuing..." %f)
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
        cmd = [GOMTREE_PATH,'-c','-p',img_rootfs]
    elif img_tar:
        cmd = [GOMTREE_PATH,'-c','-T',img_tar]
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
        cmd = [GOMTREE_PATH, '-p', img_rootfs, '-f', spec]
    elif img_tar:
        cmd = [GOMTREE_PATH,'-T',img_tar, '-f', spec]
    if keywords:
        cmd += ['-k',keywords]
    return subp(cmd)

# This is copied from the upstream python os.path.expandvars
# Expand paths containing shell variable substitutions.
# This expands the forms $variable and ${variable} only.
# Non-existent variables are left unchanged.

def expandvars(path, environ=None):
    """Expand shell variables of form $var and ${var}.  Unknown variables
    are left unchanged."""
    if not environ:
        environ = os.environ
    try:
        encoding=re.ASCII
    except AttributeError:
        encoding=re.UNICODE

    if isinstance(path, bytes):
        if b'$' not in path:
            return path
        _varprogb = re.compile(br'\$(\w+|\{[^}]*\})', encoding)
        search = _varprogb.search
        start = b'{'
        end = b'}'
    else:
        if '$' not in path:
            return path
        _varprog = re.compile(r'\$(\w+|\{[^}]*\})', encoding)
        search = _varprog.search
        start = '{'
        end = '}'
    i = 0
    while True:
        m = search(path, i)
        if not m:
            break
        i, j = m.span(0)
        name = m.group(1)
        if name.startswith(start) and name.endswith(end):
            name = name[1:-1]
        try:
            value = environ[name]
        except KeyError:
            i = j
        else:
            tail = path[j:]
            path = path[:i] + value
            i = len(path)
            path += tail
    return path

def get_registry_configs(yaml_dir):
    # Returns a dictionary of registries and a str of the default_store if applicable
    regs = {}
    default_store = None
    if not os.path.exists(yaml_dir):
        return None, default_store
    # Get list of files that end in .yaml and are in fact files
    for yaml_file in [os.path.join(yaml_dir, x) for x in os.listdir(yaml_dir) if x.endswith('.yaml')
            and os.path.isfile(os.path.join(yaml_dir, x))]:
        with open(yaml_file, 'r') as conf_file:
            try:
                temp_conf = safe_load(conf_file)
                if isinstance(temp_conf, dict):
                    def_store = temp_conf.get('default-docker', None)
                    if def_store is not None and default_store is not None:
                        raise ValueError("There are duplicate entries for 'default-docker' in {}.".format(yaml_dir))
                    elif default_store is None and def_store is not None:
                        default_store = def_store
                    registries = temp_conf.get('docker', None)
                else:
                    break
                if registries is None:
                    break
                for k,v in registries.items():
                    if k not in regs:
                        regs[k] = v
                        # Add filename of yaml into registry config
                        regs[k]['filename'] = yaml_file
                    else:
                        raise ValueError("There is a duplicate entry for {} in {}".format(k, yaml_dir))

            except ScannerError:
                raise ValueError("{} appears to not be properly formatted YAML.".format(yaml_file))
    return regs, default_store


def have_match_registry(fq_name, reg_config):
    # Returns a matching dict or None
    search_obj = fq_name
    for _ in fq_name.split('/'):
        if search_obj in reg_config:
            return reg_config[search_obj]
        search_obj = search_obj.rsplit('/', 1)[0]
    # If no match is found, returning nothing.
    return None


def get_signature_write_path(reg_info):
    # Return the defined path for where signatures should be written
    # or none if no entry is found
    return reg_info.get('sigstore-staging', reg_info.get('sigstore', None))

def get_signature_read_path(reg_info):
    # Return the defined path for where signatures should be read
    # or none if no entry is found
    return reg_info.get('sigstore', None)
