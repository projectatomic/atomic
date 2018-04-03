import argparse
import errno
import shlex
import pwd
import sys
import json
import subprocess
import collections
from contextlib import contextmanager
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
import socket
from Atomic.backends._docker_errors import NoDockerDaemon
import fcntl
import time
from string import Template

# Atomic Utility Module

ReturnTuple = collections.namedtuple('ReturnTuple',
                                     ['return_code', 'stdout', 'stderr'])
ATOMIC_CONF = os.environ.get('ATOMIC_CONF', '/etc/atomic.conf')
ATOMIC_CONFD = os.environ.get('ATOMIC_CONFD', '/etc/atomic.d/')
ATOMIC_LIBEXEC = os.environ.get('ATOMIC_LIBEXEC', '/usr/libexec/atomic')
ATOMIC_VAR_LIB = os.environ.get('ATOMIC_VAR_LIB', '/var/lib/atomic')
ATOMIC_INSTALL_JSON = os.environ.get('ATOMIC_INSTALL_JSON', os.path.join(ATOMIC_VAR_LIB, 'install.json'))

GOMTREE_PATH = os.environ.get("GOMTREE_PATH", "/usr/bin/gomtree")
RUNC_PATH = os.environ.get("RUNC_PATH", "/usr/bin/runc")
SKOPEO_PATH = os.environ.get("SKOPEO_PATH", "/usr/bin/skopeo")
KPOD_PATH = os.environ.get("KPOD_PATH", "/usr/bin/kpod")
CAPSH_PATH = os.environ.get("CAPSH_PATH", "/usr/sbin/capsh")

try:
    from subprocess import DEVNULL  # pylint: disable=no-name-in-module
except ImportError:
    DEVNULL = open(os.devnull, 'wb')

def gomtree_available():
    return os.path.exists(GOMTREE_PATH)

def runc_available():
    return os.path.exists(RUNC_PATH)

def check_if_python2():
    if int(sys.version_info[0]) < 3:
        _input = raw_input # pylint: disable=undefined-variable,raw_input-builtin
        return _input, True
    else:
        _input = input
        return _input, False

input, is_python2 = check_if_python2() # pylint: disable=redefined-builtin


def get_docker_conf():
    dconf = []
    with AtomicDocker() as c:
        dconf = c.info()
    return dconf


def registries_tool_path():
    registries_path = get_atomic_config_item(['registries_binary']) or "/usr/libexec/registries"
    if os.path.exists(registries_path):
        return registries_path
    try:
        return subprocess.check_output(['which', '--skip-alias','registries'], stderr=DEVNULL)
    except subprocess.CalledProcessError:
        return None

def load_registries_from_yaml():
    # Returns in JSON
    try:
        return json.loads(check_output([registries_tool_path(), '-j']).decode('utf-8'))
    except subprocess.CalledProcessError:
        return json.loads({})

def get_registries():
    registries = []
    if registries_tool_path() is not None:
        registries_json = load_registries_from_yaml()
        # Eliminate any duplicates with set.
        if "registries.search" in registries_json:
            # We are dealing with toml
            _registries = list(set(registries_json.get("registries.search", []).get("registries", [])))
            _insecure_registries = list(set(registries_json.get("registries.insecure", []).get("registries", [])))
            _blocked_registries= list(set(registries_json.get("registries.block", []).get("registries", [])))
        else:
            # We are dealing with yaml
            _registries = list(set(registries_json.get("registries", [])))
            _insecure_registries = list(set(registries_json.get('insecure_registries', [])))
            _blocked_registries = list(set(registries_json.get('block_registries', [])))
        duplicate_secure_insecure = list(set(_registries).intersection(_insecure_registries))
        if len(duplicate_secure_insecure) > 0:
            raise ValueError("There are duplicate values for registries and insecure registries.  Please correct "
                             "in registries.conf.")
        registries = [{'search': True, 'hostname': x, 'name': x, 'secure': True} for x in _registries if x not in _blocked_registries]
        registries += [{'search': True, 'hostname': x, 'name': x, 'secure': True} for x in _insecure_registries if x not in _blocked_registries]
        if 'docker.io' not in _registries and 'docker.io' not in _blocked_registries:  # Always add docker.io unless blocked
            registries.append({'hostname': 'registry-1.docker.io', 'name': 'docker.io', 'search': True, 'secure': True})
    elif is_backend_available('docker'):
        dconf = get_docker_conf()
        search_regs = [x['Name'] for x in dconf['Registries']] if 'Registries' in dconf else ['docker.io']
        rconf = dconf['RegistryConfig']['IndexConfigs']
        # docker.io is special
        if 'docker.io' in rconf:
            registries.append({'hostname': 'registry-1.docker.io', 'name': 'docker.io', 'search': True, 'secure': True})
            # remove docker.io
            del(rconf['docker.io'])
        for i in rconf:
            search_bool = True if i in search_regs else False
            registries.append({'hostname': i, 'name': i, 'search': search_bool, 'secure': rconf[i]['Secure'] })
    return registries


def is_backend_available(backend):
    # Local import to avoid circular imports
    import Atomic.backendutils as backendutils
    beu = backendutils.BackendUtils()
    if backend in [x().backend for x in beu.available_backends]:
        return True
    return False

def check_storage_is_available(storage):
    if not is_backend_available(storage):
        raise ValueError("The storage backend '{}' is not available.  "
                         "Try with an alternate storage with --storage if available.".format(storage))

def image_by_name(img_name, images=None):
    # Returns a list of image data for images which match img_name. Will
    # optionally take a list of images from a docker.Client.images
    # query to avoid multiple docker queries.
    i_reg, i_rep, i_img, i_tag, _ = Decompose(img_name).all

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
    possible_images = []
    for i in images:
        if not i["RepoTags"]:
            continue
        if img_name in i['RepoTags']:
            return [i]
        for t in i['RepoTags']:
            reg, rep, d_image, tag, _ = Decompose(t).all
            if matches(reg, i_reg) \
                    and matches(rep, i_rep) \
                    and matches(tag, i_tag) \
                    and matches(d_image, i_img):
                valid_images.append(i)
                break
            if matches(i_img, d_image) and matches(i_tag, tag) and reg == "":
                valid_images.append(i)
                break
            if matches(i_img, d_image) and matches(i_tag, tag):
                possible_images.append(i)
                break

    if len(valid_images) > 0:
        return valid_images
    if len(possible_images) == 1:
        return possible_images
    return []


def subp(cmd, cwd=None, newline=False):
    # Run a command as a subprocess.
    # Return a triple of return code, standard out, standard err.
    proc = subprocess.Popen(cmd, cwd=cwd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, close_fds=True,
                            universal_newlines=newline,
                            env=os.environ)
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
    if not isinstance(cmd, (list, tuple)):
        try:
            cmd = shlex.split(cmd)
        except Exception as ex:
            raise ValueError("Command '{}' is not valid: {!r}".format(cmd, ex))
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

def skopeo_inspect(image, args=None, return_json=True, newline=False):
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
    cmd = [SKOPEO_PATH,  'inspect', '--tls-verify=false']+ args + [image]
    try:
        results = subp(cmd, newline=newline)
    except OSError:
        raise ValueError("skopeo must be installed to perform remote inspections")
    if results.return_code is not 0:
        error = SkopeoError(results.stderr.decode('utf-8').rstrip()).msg
        if error == "":
            error = results.stderr.decode('utf-8').rstrip()
        raise ValueError(error)
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

    cmd = [SKOPEO_PATH, 'delete', '--tls-verify=false'] + args + [image] # pylint: disable=invalid-unary-operand-type
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
    cmd = [SKOPEO_PATH]
    if debug:
        cmd = cmd + ['--debug']
    cmd = cmd + ['standalone-sign', manifest_file_name, image,
                 fingerprint, "-o", signature_path]
    if debug:
        write_out("Executing: {}".format(" ".join(cmd)))
    return check_call(cmd, env=os.environ)

def skopeo_manifest_digest(manifest_file, debug=False):
    cmd = [SKOPEO_PATH]
    if debug:
        cmd = cmd + ['--debug']
    cmd = cmd  + ['manifest-digest', manifest_file]
    return check_output(cmd).rstrip().decode()

def skopeo_copy(source, destination, debug=False, sign_by=None, insecure=False, policy_filename=None,
                username=None, password=None, gpghome=None, dest_ostree_tmp_dir=None, src_creds=None):

    cmd = [SKOPEO_PATH]
    if policy_filename:
        cmd = cmd + [ "--policy=%s" % policy_filename ]

    if debug:
        cmd = cmd + ['--debug']
    cmd = cmd + ['copy']
    if insecure:
        cmd = cmd + ['--src-tls-verify=false', '--dest-tls-verify=false']
    if username:
        # it's ok to send an empty password (think of krb for instance)
        cmd = cmd + [ "--dest-creds=%s%s" % (username, ":%s" % password if password else "") ]
    if destination.startswith("docker"):
        cmd = cmd + ['--remove-signatures']
    elif destination.startswith("atomic") and not sign_by:
        cmd = cmd + ['--remove-signatures']

    if src_creds:
        cmd = cmd + ['--src-creds', src_creds]

    if sign_by:
        cmd = cmd + ['--sign-by', sign_by]

    if dest_ostree_tmp_dir:
        cmd = cmd + ['--dest-ostree-tmp-dir', dest_ostree_tmp_dir]
    cmd = cmd + [source, destination]
    if debug:
        write_out("Executing: {}".format(" ".join(cmd)))
    if gpghome is not None:
        os.environ['GNUPGHOME'] = gpghome
    return check_call(cmd, env=os.environ)



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

def add_opt(sub):
    sub.add_argument("--opt1", dest="opt1",help=argparse.SUPPRESS)
    sub.add_argument("--opt2", dest="opt2",help=argparse.SUPPRESS)
    sub.add_argument("--opt3", dest="opt3",help=argparse.SUPPRESS)

def get_atomic_config_item(config_items, atomic_config=None, default=None):
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
                yaml_struct = yaml_struct[i.lower()]
        except KeyError:
            try:
                yaml_struct = yaml_struct[i.upper()]
            except KeyError:
                return None
        return yaml_struct
    if atomic_config is None:
        atomic_config = get_atomic_config()
    val = _recursive_get(atomic_config, config_items)
    if val:
        return val
    else:
        return default

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
        if os.path.exists("/var/lib/docker"):
            docker = "docker"
        else:
            docker = "docker-latest"

        default_docker.cache = atomic_config.get('default_docker', docker)
    return default_docker.cache
default_docker.cache = None

def default_docker_lib():
    try:
        return get_docker_conf()["DockerRootDir"]
    except (NoDockerDaemon, requests.ConnectionError):
        # looks like dockerd is not running
        pass

    if not default_docker_lib.cache:
        dockerlib_path = "/var/lib/%s" % default_docker()
        if os.path.exists(dockerlib_path):
            default_docker_lib.cache = dockerlib_path
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
        if e.args[0].args[0] == errno.ENOENT: # pylint: disable=no-member
            raise ValueError("Image not found")
    return None

def is_user_mode():
    return os.geteuid() != 0

def generate_validation_manifest(img_rootfs=None, img_tar=None, keywords="", debug=False):
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
    if debug:
        write_out(" ".join(cmd))
    return subp(cmd)

def validate_manifest(spec, img_rootfs=None, img_tar=None, keywords="", json_out=False, debug=False):
    """
    Executes the gomtree validation manife  st validation command
    :param spec: path to spec file
    :param img_rootfs: path to directory
    :param img_tar: path to tar file (or tgz file)
    :param keywords: use only the keywords specified to validate the manifest
    :param json_out: Return the validation in JSON form
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
    if json_out:
        cmd += ['-result-format', 'json']
    if debug:
        write_out(" ".join(cmd))
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
    """
    Get concatenated registries.d sigstore configuration as a single dict of all files
    :param yaml_dir: sigstore directory, e.g. /etc/containers/registries.d
    :return: tuple (a dictionary of sigstores, str or None of the default_store)
    """
    regs = {}
    default_store = None
    if not os.path.exists(yaml_dir):
        return regs, default_store
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

def strip_port(_input):
    ip, _, _ = _input.rpartition(':')
    if ip == '':
        return _input
    return ip.strip("[]")

def is_insecure_registry(registry_config, registry):
    if registry is "":
        raise ValueError("Registry value cannot be blank")
    if is_python2 and not isinstance(registry, unicode): #pylint: disable=undefined-variable,unicode-builtin
        registry = unicode(registry) #pylint: disable=unicode-builtin,undefined-variable
    insecure_registries = [x for x in registry_config['IndexConfigs'] if registry_config['IndexConfigs'][x]['Secure'] is False]

    # Be only as good as docker
    if registry in insecure_registries:
        return True
    return False

def is_valid_image_uri(uri, qualifying=None):
    '''
    Parse and validate image URI
    :return: parsed URI
    '''
    try:
        from urlparse import urlparse #pylint: disable=import-error
    except ImportError:
        from urllib.parse import urlparse #pylint: disable=no-name-in-module,import-error
    min_attributes = ('scheme', 'netloc')
    qualifying = min_attributes if qualifying is None else qualifying
    # does it parse?
    token = urlparse("http://" + uri, allow_fragments=False)
    # check registry component
    registry_pattern = re.compile(r'^[a-zA-Z0-9-_\.]+\/?:?[0-9]*[a-z0-9-\/:]*$')
    if not re.search(registry_pattern, token.netloc):
        raise ValueError("Invalid registry format")
    # check repository component
    path_pattern = re.compile(r'^[a-z0-9-:\./]*$')
    if not re.search(path_pattern, token.path):
        raise ValueError("Invalid repository format")
    return all([getattr(token, qualifying_attr)
                for qualifying_attr in qualifying])

def getgnuhome():
    defaulthome = get_atomic_config_item(['gnupg_homedir'])
    if defaulthome:
        return defaulthome

    try:
        fd=open("/proc/self/loginuid")
        uid=int(fd.read())
        fd.close()
        return ("%s/.gnupg" % pwd.getpwuid(uid).pw_dir)
    except (KeyError, IOError):
        if "SUDO_UID" in os.environ:
            uid = int(os.environ["SUDO_UID"])
        else:
            uid = os.getuid()
    try:
        return ("%s/.gnupg" % pwd.getpwuid(uid).pw_dir)
    except KeyError:
        return None


def confirm_input(msg):
    write_out("{}\n".format(msg))
    confirm = input("\nConfirm (y/N)")
    return confirm.strip().lower() in ['y', 'yes']


def load_scan_result_file(file_name):
    """
    Read a specific json file
    """
    return json.loads(open(os.path.join(file_name), "r").read())


@contextmanager
def file_lock(path):
    lock_file_name = "{}.lock".format(path)
    time_out = 0
    f_lock = False
    with open(lock_file_name, "a") as f:
        while time_out < 10.5: # Ten second attempt to get a lock
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                f_lock = True
                break
            except IOError:
                time.sleep(.5)
                time_out += .5
        if not f_lock:
            raise ValueError("Unable to get file lock for {}".format(lock_file_name))

        # Call the user code
        yield
        # Now unlock
        fcntl.flock(f, fcntl.LOCK_UN)

# Records additional data for containers outside of the native storage (docker/ostree)
class InstallData(object):

    @classmethod
    def read_install_data_locked(cls):
        try:
            with open(ATOMIC_INSTALL_JSON, 'r') as f:
                # Backwards compatibility - we previously created an empty file explicitly;
                # see https://github.com/projectatomic/atomic/pull/966
                if os.fstat(f.fileno()).st_size == 0:
                    return {}
                data = json.load(f)
                # Backwards compatibility - we supported only one container per image
                # if the file is stored in the old format, then automatically convert
                # it to the new format where each image name can refer to a list of
                # installed containers.
                for k, v in data.items():
                    if isinstance(v, dict):
                        data[k] = [v]
                return data
        except IOError as e:
            if e.errno == errno.ENOENT:
                return {}
            raise e

    @classmethod
    def read_install_data(cls):
        with file_lock(ATOMIC_INSTALL_JSON):
            return cls.read_install_data_locked()

    @classmethod
    def write_install_data_locked(cls, new_data, append=False):
        install_data = cls.read_install_data_locked()
        if not append:
            install_data = new_data
        else:
            for k, v in new_data.items():
                if k not in install_data:
                    install_data[k] = []
                for index, c in enumerate(install_data[k]):
                    if c.get('container_name') == v.get('container_name') and c.get('id') == v.get('id'):
                        del install_data[k][index]
                        break
                install_data[k].append(v)
        temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False)

        json.dump(install_data, temp_file)
        temp_file.close()
        if not os.path.exists(ATOMIC_VAR_LIB):
            os.makedirs(ATOMIC_VAR_LIB)
        shutil.move(temp_file.name, ATOMIC_INSTALL_JSON)

    @classmethod
    def write_install_data(cls, new_data, append=False):
        with file_lock(ATOMIC_INSTALL_JSON):
            return cls.write_install_data_locked(new_data, append)

    @classmethod
    def get_install_data_by_id(cls, iid):
        install_data = cls.read_install_data()
        for installed_image in install_data:
            containers = install_data[installed_image]
            for container in containers:
                if container['id'] == iid:
                    return container
        raise ValueError("Unable to find {} in installed image data ({}). Re-run command with -i to ignore".format(iid, ATOMIC_INSTALL_JSON))

    @classmethod
    def get_install_name_by_id(cls, iid, install_data=None):
        if not install_data:
            install_data = cls.read_install_data()
        for installed_image in install_data:
            containers = install_data[installed_image]
            for container in containers:
                if container['id'] == iid:
                    return installed_image
        raise ValueError("Unable to find {} in installed image data ({}). Re-run command with -i to ignore".format(iid, ATOMIC_INSTALL_JSON))

    @classmethod
    def delete_by_id(cls, iid, name, ignore=False):
        last_image = False
        with file_lock(ATOMIC_INSTALL_JSON):
            install_data = cls.read_install_data_locked()
            for installed_image in install_data:
                containers = install_data[installed_image]
                if not name and len(containers) > 1:
                    raise ValueError("Name not specified but more than one container installed")

                for index, container in enumerate(containers):
                    if name is not None and container['container_name'] != name:
                        continue
                    if container['id'] == iid:
                        del containers[index]
                        install_data[installed_image] = containers
                        if len(containers) == 0:
                            del install_data[installed_image]
                            last_image = True
                        cls.write_install_data_locked(install_data)
                        return last_image
        if not ignore:
            raise ValueError("Unable to find {} in the installed containers".format(iid))

    @classmethod
    def image_installed(cls, img_object):
        install_data = cls.read_install_data()
        if install_data.get(img_object.id, None):
            return True
        if install_data.get(img_object.input_name, None):
            return True
        if install_data.get(img_object.name, None):
            return True
        if install_data.get(img_object.image, None):
            return True
        if install_data.get("{}:{}".format(img_object.input_name, img_object.tag), None):
            return True
        try:
            from Atomic.discovery import RegistryInspectError
            if install_data.get(img_object.fq_name, None):
                return True
        except RegistryInspectError:
            pass
        return False

class Decompose(object):
    """
    Class for decomposing an input string in its respective parts like registry,
    repository, image, tag, and digest.

    return: Nothing by default

    Example usage:
        registry, repo, image, tag, digest = Decompose("docker.io/library/busybox:latest").all
        repo = Decompose("docker.io/library/busybox:latest").repo
        digest = Decompose("docker.io/fedora@sha256:64a02df6aac27d1200c2...67ce4af994ba5dc3669e").digest
    """

    def __init__(self, input_name):
        self._registry = None
        self._repo = None
        self._image = None
        self._tag = None
        self._digest = None
        self._decompose(input_name)

    def _decompose(self, input_name):
        def is_network_address(_input):
            try:
                socket.gethostbyname(strip_port(_input))
            except socket.gaierror:
                if _input in [x['hostname'] for x in get_registries()]:
                    return True
                return False
            return True

        # Skopeo requires http: if the image is insecure. However,
        # parsing fails when http: remains in the input_name
        input_name = remove_skopeo_prefixes(input_name)
        reg, repo, image, tag = '', input_name, '', ''
        digest = None
        if '/' in repo:
            reg, repo = repo.split('/', 1)
            if not is_network_address(reg):
                repo = '{}/{}'.format(reg, repo)
                reg = ''
        if '@sha256:' in repo:
            repo, _, digest = repo.rpartition("@")

        if ':' in repo:
            repo, tag = repo.rsplit(':', 1)
        if "/" in repo:
            repo, image = repo.rsplit("/", 1)
        if not image and repo:
            image = repo
            repo = ''
        if reg == 'docker.io' and repo == '':
            repo = 'library'
            implicit_repo = True
        else:
            implicit_repo = False
        if not tag and not digest:
            tag = "latest"

        if reg and not repo and not is_network_address(repo):
            repo = reg
            reg = ''

        self._registry = str(reg) if reg else ''
        self._repo = str(repo) if repo else ''
        self._image = str(image) if image else ''
        self._tag = str(tag) if tag else ''
        self._digest = str(digest) if digest else ''
        if not implicit_repo and self._repo:
            self._image_with_repo = "%s/%s" % (self._repo, self._image)
        else:
            self._image_with_repo = self._image

        if self._tag and self._digest:
            raise ValueError("An image name cannot have both a tag and manifest digest in its name")

    @property
    def registry(self):
        return self._registry

    @property
    def repo(self):
        return self._repo

    @property
    def image(self):
        return self._image

    @property
    def tag(self):
        return self._tag

    @property
    def digest(self):
        return self._digest

    @property
    def image_with_repo(self):
        return self._image_with_repo

    @property
    def no_tag(self):
        result = self._registry
        if self._repo:
            result += "/{}".format(self._repo)
        result += "/{}".format(self._image)
        return result

    @property
    def all(self):
        return self._registry, self._repo, self._image, self._tag, self._digest


class SkopeoError(object):
    def __init__(self, string_error):
        self.msg = ""
        for line in shlex.split(string_error):
            key, _, msg = line.partition("=")
            setattr(self, key, msg)

def write_template(inputfilename, data, values, destination):
    if destination:
        try:
            os.makedirs(os.path.dirname(destination))
        except OSError:
            pass

    template = Template(data)
    try:
        result = template.substitute(values)
    except KeyError as e:
        raise ValueError("The template file '%s' still contains an unreplaced value for: '%s'" % \
                         (inputfilename, str(e)))

    if destination is not None:
        with open(destination, "w") as outfile:
            outfile.write(result)
        return result
    return None

def get_proxy():
    """
    Returns proxy information from environment variables as a dict
    """
    def _get_envs_capped():
        return {k.upper(): v for k,v in os.environ.items()}

    proxies = {}
    envs = _get_envs_capped()

    # Environment variables should override configuration items
    proxies['http'] = get_atomic_config_item(['HTTP_PROXY']) if 'HTTP_PROXY' not in envs else envs['HTTP_PROXY']
    proxies['https'] = get_atomic_config_item(['HTTPS_PROXY']) if 'HTTPS_PROXY' not in envs else envs['HTTPS_PROXY']
    proxies['no_proxy'] = get_atomic_config_item(['NO_PROXY']) if 'NO_PROXY' not in envs else envs['NO_PROXY']
    return proxies

def set_proxy():
    """
    Sets proxy as environment variable if not set already
    """
    proxies = get_proxy()
    if proxies['http'] and 'HTTP_PROXY' not in os.environ:
        os.environ['HTTP_PROXY'] = proxies['http']
    if proxies['https'] and 'HTTPS_PROXY' not in os.environ:
        os.environ['HTTPS_PROXY'] = proxies['https']
    if proxies['no_proxy'] and 'NO_PROXY' not in os.environ:
        os.environ['NO_PROXY'] = proxies['no_proxy']

    return proxies

class ImageAlreadyExists(Exception):
    def __init__(self, img):
        super(ImageAlreadyExists, self).__init__("The latest version of image {} already exists.".format(img))


def kpod(cmd, storage=None, debug=None):
    if not isinstance(cmd, list):
        cmd = cmd.split()
    _kpod = [KPOD_PATH]
    if storage is not None:
        _kpod += ["-s", storage]
    _kpod += cmd
    if debug:
        write_out(" ".join(cmd))
    return check_output(_kpod, env=os.environ)


def remove_skopeo_prefixes(image):
    """
    Remove prefixes that map to skopeo args but not expected
    in other image uses.

    :param image: The full image string
    :type image: str
    :returns: The image string without prefixes
    :rtype: str
    """
    for remove in ('oci:', 'http:', 'https:'):
        if image.startswith(remove):
            image = image.replace(remove, '')
    return image

KNOWN_CAPS = ['CAP_CHOWN',
              'CAP_DAC_OVERRIDE',
              'CAP_DAC_READ_SEARCH',
              'CAP_FOWNER',
              'CAP_FSETID',
              'CAP_KILL',
              'CAP_SETGID',
              'CAP_SETUID',
              'CAP_SETPCAP',
              'CAP_LINUX_IMMUTABLE',
              'CAP_NET_BIND_SERVICE',
              'CAP_NET_BROADCAST',
              'CAP_NET_ADMIN',
              'CAP_NET_RAW',
              'CAP_IPC_LOCK',
              'CAP_IPC_OWNER',
              'CAP_SYS_MODULE',
              'CAP_SYS_RAWIO',
              'CAP_SYS_CHROOT',
              'CAP_SYS_PTRACE',
              'CAP_SYS_PACCT',
              'CAP_SYS_ADMIN',
              'CAP_SYS_BOOT',
              'CAP_SYS_NICE',
              'CAP_SYS_RESOURCE',
              'CAP_SYS_TIME',
              'CAP_SYS_TTY_CONFIG',
              'CAP_MKNOD',
              'CAP_LEASE',
              'CAP_AUDIT_WRITE',
              'CAP_AUDIT_CONTROL',
              'CAP_SETFCAP',
              'CAP_MAC_OVERRIDE',
              'CAP_MAC_ADMIN',
              'CAP_SYSLOG',
              'CAP_WAKE_ALARM',
              'CAP_BLOCK_SUSPEND',
              'CAP_AUDIT_READ']

def get_all_known_process_capabilities():
    """
    Get all the known process capabilities

    :returns: The list of known capabilities
    :rtype: list
    """

    with open("/proc/sys/kernel/cap_last_cap", 'r') as f:
        last_cap = int(f.read())

    if last_cap < len(KNOWN_CAPS):
        caps = KNOWN_CAPS[:last_cap+1]
    else:
        mask = hex((1 << (last_cap + 1)) - 1)
        out = subprocess.check_output([CAPSH_PATH, '--decode={}'.format(mask)], stderr=DEVNULL)

        # The output looks like 0x0000003fffffffff=cap_chown,cap_dac_override,...
        # so take only the part after the '='
        caps = str(out.decode().split("=")[1].strip()).split(',')

    caps_list = [i.upper() for i in caps]

    return [i for i in caps_list if not i[0].isdigit()]
