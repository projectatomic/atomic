import os
import sys
import json
from . import util
import tempfile
import tarfile
from string import Template
import calendar
import shutil
import stat
import subprocess
import time
from .client import AtomicDocker
from ctypes import cdll, CDLL

try:
    import gi
    try:
        gi.require_version('OSTree', '1.0')
        from gi.repository import Gio, GLib, OSTree  # pylint: disable=no-name-in-module
        OSTREE_PRESENT = True
    except ValueError:
        OSTREE_PRESENT = False
except ImportError:
    OSTREE_PRESENT = False

try:
    from subprocess import DEVNULL  # pylint: disable=no-name-in-module
except ImportError:
    DEVNULL = open(os.devnull, 'wb')

HOME = os.path.expanduser("~")

ATOMIC_LIBEXEC = os.environ.get('ATOMIC_LIBEXEC', '/usr/libexec/atomic')
ATOMIC_VAR = '/var/lib/containers/atomic'
ATOMIC_VAR_USER = "%s/.containers/atomic" % HOME
OSTREE_OCIIMAGE_PREFIX = "ociimage/"
SYSTEMD_UNIT_FILES_DEST = "/etc/systemd/system"
SYSTEMD_UNIT_FILES_DEST_USER = "%s/.config/systemd/user" % HOME
SYSTEMD_TMPFILES_DEST = "/etc/tmpfiles.d"
SYSTEMD_TMPFILES_DEST_USER = "%s/.containers/tmpfiles" % HOME
SYSTEMD_UNIT_FILE_DEFAULT_TEMPLATE = """
[Unit]
Description=$NAME

[Service]
ExecStart=$EXEC_START
ExecStop=$EXEC_STOP
Restart=on-crash
WorkingDirectory=$DESTDIR

[Install]
WantedBy=multi-user.target
"""
TEMPLATE_FORCED_VARIABLES = ["DESTDIR", "NAME", "EXEC_START", "EXEC_STOP",
                             "HOST_UID", "HOST_GID"]
TEMPLATE_OVERRIDABLE_VARIABLES = ["RUN_DIRECTORY", "STATE_DIRECTORY"]

class SystemContainers(object):

    def __init__(self):
        self.atomic_config = util.get_atomic_config()
        self.backend = None
        self.user = util.is_user_mode()
        self.args = None
        self.setvalues = None
        self.display = False

    def get_atomic_config_item(self, config_item):
        return util.get_atomic_config_item(config_item, atomic_config=self.atomic_config)

    def _do_syncfs(self, rootfs, rootfs_fd):
        # Fallback to sync --file-system if loading it from libc fails.
        try:
            cdll.LoadLibrary("libc.so.6")
            libc = CDLL("libc.so.6")
            if libc.syncfs(rootfs_fd) == 0:
                return
        except (NameError, AttributeError, OSError):
            pass

        util.check_call(["sync", "--file-system", rootfs], stdin=DEVNULL,
                        stdout=DEVNULL,
                        stderr=DEVNULL)

    def _checkout_layer(self, repo, rootfs_fd, rootfs, rev):
        # ostree 2016.8 has a glib introspection safe API for checkout, use it
        # when available.
        if hasattr(repo, "checkout_at"):
            options = OSTree.RepoCheckoutAtOptions() # pylint: disable=no-member
            options.overwrite_mode = OSTree.RepoCheckoutOverwriteMode.UNION_FILES
            options.process_whiteouts = True
            options.disable_fsync = True
            if self.user:
                options.mode = OSTree.RepoCheckoutMode.USER
            repo.checkout_at(options, rootfs_fd, rootfs, rev)
        else:
            if self.user:
                user = ["--user-mode"]
            else:
                user = []
            util.check_call(["ostree", "--repo=%s" % self.get_ostree_repo_location(),
                             "checkout",
                             "--union"] +
                            user +
                             ["--whiteouts",
                              "--fsync=no",
                              rev,
                              rootfs],
                            stdin=DEVNULL,
                            stdout=DEVNULL,
                            stderr=DEVNULL)

    def set_args(self, args):
        self.args = args

        try:
            self.backend = args.backend
        except (NameError, AttributeError):
            self.backend = None
        if not self.backend:
            self.backend = self.get_atomic_config_item(["default_storage"]) or "ostree"

        try:
            self.display = self.args.display
        except (NameError, AttributeError):
            pass

        try:
            self.setvalues = args.setvalues
        except (NameError, AttributeError):
            pass

    def _pull_image_to_ostree(self, repo, image, upgrade):
        if not repo:
            raise ValueError("Cannot find a configured OSTree repo")
        if image.startswith("ostree:"):
            self._check_system_ostree_image(repo, image, upgrade)
        elif image.startswith("docker:"):
            image = self._pull_docker_image(repo, image.replace("docker:", "", 1))
        elif image.startswith("dockertar:"):
            image = self._pull_docker_tar(repo, image.replace("dockertar:", "", 1))
        else: # Assume "oci:"
            self._check_system_oci_image(repo, image, upgrade)
        return image

    def pull_image(self, image=None):
        self._pull_image_to_ostree(self._get_ostree_repo(), image or self.args.image, True)

    def install_user_container(self, image, name):
        try:
            util.check_call([util.BWRAP_OCI_PATH, "--version"], stdout=DEVNULL)
        except util.FileNotFound:
            raise ValueError("Cannot install the container: bwrap-oci is needed to run user containers")

        if not "--user" in str(util.check_output(["systemctl", "--help"], stdin=DEVNULL, stderr=DEVNULL)):
            raise ValueError("Cannot install the container: systemctl does not support --user")

        # Same entrypoint
        return self.install(image, name)

    def install(self, image, name):
        repo = self._get_ostree_repo()
        if not repo:
            raise ValueError("Cannot find a configured OSTree repo")

        if self.args.system and self.user:
            raise ValueError("Only root can use --system")

        if not self.user:
            try:
                util.check_call([util.RUNC_PATH, "--version"], stdout=DEVNULL)
            except util.FileNotFound:
                raise ValueError("Cannot install the container: runc is needed to run system containers")

        image = self._pull_image_to_ostree(repo, image, False)

        if self.get_checkout(name):
            util.write_out("%s already present" % (name))
            return

        return self._checkout(repo, name, image, 0, False, remote=self.args.remote)

    def _check_oci_configuration_file(self, conf_path, remote=None):
        with open(conf_path, 'r') as conf:
            try:
                configuration = json.loads(conf.read())
            except ValueError:
                raise ValueError("Invalid json in configuration file: {}.".format(conf_path))
        if not 'root' in configuration or \
           not 'readonly' in configuration['root'] or \
           not configuration['root']['readonly']:
            raise ValueError("Invalid configuration file.  Only readonly images are supported")
        if configuration['root']['path'] != 'rootfs' and not remote:
            raise ValueError("Invalid configuration file.  Path must be 'rootfs'")

        missing_source_paths = []
        # Ensure that the source path specified in bind/rbind exists
        if "mounts" in configuration:
            for mount in configuration["mounts"]:
                if not "type" in mount:
                    continue
                if "source" in mount and "bind" in mount["type"]:
                    source = mount["source"]
                    if not os.path.exists(source):
                        missing_source_paths.append(source)
        return missing_source_paths

    def _generate_default_oci_configuration(self, destination):
        args = [util.RUNC_PATH, 'spec']
        util.subp(args, cwd=destination)
        conf_path = os.path.join(destination, "config.json")
        with open(conf_path, 'r') as conf:
            configuration = json.loads(conf.read())
        configuration['root']['readonly'] = True
        configuration['root']['path'] = 'rootfs'
        configuration['process']['terminal'] = False
        configuration['process']['args'] = ['run.sh']
        with open(conf_path, 'w') as conf:
            conf.write(json.dumps(configuration, indent=4))

    def _generate_systemd_startstop_directives(self, name):
        if self.user:
            return ["%s '%s'" % (util.BWRAP_OCI_PATH, name), ""]

        version = str(util.check_output([util.RUNC_PATH, "--version"], stderr=DEVNULL))
        if "version 0" in version:
            runc_commands = ["start", "kill"]
        else:
            runc_commands = ["run", "kill"]
        return ["%s %s '%s'" % (util.RUNC_PATH, command, name) for command in runc_commands]

    def _get_systemd_destination_files(self, name):
        if self.user:
            unitfileout = os.path.join(SYSTEMD_UNIT_FILES_DEST_USER, "%s.service" % name)
            tmpfilesout = os.path.join(SYSTEMD_TMPFILES_DEST_USER, "%s.conf" % name)
        else:
            unitfileout = os.path.join(SYSTEMD_UNIT_FILES_DEST, "%s.service" % name)
            tmpfilesout = os.path.join(SYSTEMD_TMPFILES_DEST, "%s.conf" % name)
        return unitfileout, tmpfilesout

    def _resolve_remote_path(self, remote_path):
        if not remote_path:
            return None

        real_path = os.path.realpath(remote_path)
        if not os.path.exists(real_path):
            raise ValueError("The container's rootfs is set to remote, but the remote rootfs does not exist")
        return real_path

    def _checkout(self, repo, name, img, deployment, upgrade, values=None, destination=None, extract_only=False, remote=None):
        destination = destination or "%s/%s.%d" % (self._get_system_checkout_path(), name, deployment)
        unitfileout, tmpfilesout = self._get_systemd_destination_files(name)

        if not upgrade:
            for f in [unitfileout, tmpfilesout]:
                if os.path.exists(f):
                    raise ValueError("The file %s already exists." % f)

        try:
            return self._do_checkout(repo, name, img, upgrade, values, destination, unitfileout, tmpfilesout, extract_only, remote)
        except (ValueError, OSError) as e:
            try:
                if not extract_only:
                    shutil.rmtree(destination)
            except OSError:
                pass
            try:
                if not extract_only and not upgrade:
                    shutil.rmtree(unitfileout)
            except OSError:
                pass
            try:
                if not extract_only and not upgrade:
                    shutil.rmtree(tmpfilesout)
            except OSError:
                pass
            raise e

    # Accept both name and version Id, and return the ostree rev
    def _resolve_image(self, repo, img):
        imagebranch = SystemContainers._get_ostree_image_branch(img)
        rev = repo.resolve_rev(imagebranch, True)[1]
        if rev:
            return imagebranch, rev

        # if we could not find an image with the specified name, check if it is the prefix
        # of an ID, and allow it only for tagged images.
        if not str.isalnum(str(img)):
            return None, None

        tagged_images = [i for i in self.get_system_images(get_all=True, repo=repo) if i['RepoTags']]
        matches = [i for i in tagged_images if i['Id'].startswith(img)]
        if len(matches) == 1:
            # only one image, use it
            i = matches[0]
            imagebranch = "%s%s" % (OSTREE_OCIIMAGE_PREFIX, SystemContainers._encode_to_ostree_ref(i['RepoTags'][0]))
            return imagebranch, i['OSTree-rev']
        elif len(matches) > 1:
            # more than one match, error out
            raise ValueError("more images matching prefix `%s`" % img)
        return None, None

    def _do_checkout(self, repo, name, img, upgrade, values, destination, unitfileout, tmpfilesout, extract_only, remote):
        if not values:
            values = {}

        remote_path = self._resolve_remote_path(remote)

        _, rev = self._resolve_image(repo, img)
        if rev is None:
            raise ValueError("Image %s not found" % img)

        if remote_path:
            remote_rootfs = os.path.join(remote_path, "rootfs")
            if os.path.exists(remote_rootfs):
                util.write_out("The remote rootfs for this container is set to be %s" % remote_rootfs)
            elif os.path.exists(os.path.join(remote, "usr")): # Assume that the user directly gave the location of the rootfs
                remote_rootfs = remote
                remote_path = os.path.dirname(remote_path) # Use the parent directory as the "container location"
            else:
                raise ValueError("--remote was specified but the given location does not contain a rootfs")
            exports = os.path.join(remote_path, "rootfs/exports")
        else:
            exports = os.path.join(destination, "rootfs/exports")

        unitfile = os.path.join(exports, "service.template")
        tmpfiles = os.path.join(exports, "tmpfiles.template")

        util.write_out("Extracting to %s" % destination)

        # upgrade will not restart the service if it was not already running
        was_service_active = self._is_service_active(name)

        if self.display:
            return

        if self.user:
            rootfs = os.path.join(destination, "rootfs")
        elif extract_only:
            rootfs = destination
        elif remote_path:
            rootfs = os.path.join(remote_path, "rootfs")
        else:
            # Under Atomic, get the real deployment location if we're using the
            # system repo. It is needed to create the hard links.
            if self.get_ostree_repo_location() == '/ostree/repo':
                try:
                    sysroot = OSTree.Sysroot()
                    sysroot.load()
                    osname = sysroot.get_booted_deployment().get_osname()
                    destination = os.path.join("/ostree/deploy/", osname, os.path.relpath(destination, "/"))
                    destination = os.path.realpath(destination)
                except: #pylint: disable=bare-except
                    pass
            rootfs = os.path.join(destination, "rootfs")

        if os.path.exists(destination):
            shutil.rmtree(destination)

        if remote_path:
            os.makedirs(destination)
        else:
            os.makedirs(rootfs)

        manifest = self._image_manifest(repo, rev)

        if not remote_path:
            rootfs_fd = None
            try:
                rootfs_fd = os.open(rootfs, os.O_DIRECTORY)
                if manifest is None:
                    self._checkout_layer(repo, rootfs_fd, rootfs, rev)
                else:
                    layers = SystemContainers.get_layers_from_manifest(json.loads(manifest))
                    for layer in layers:
                        rev_layer = repo.resolve_rev("%s%s" % (OSTREE_OCIIMAGE_PREFIX, layer.replace("sha256:", "")), True)[1]
                        if not rev_layer:
                            raise ValueError("Layer not found: %s.  Please pull again the image" % layer.replace("sha256:", ""))

                        self._checkout_layer(repo, rootfs_fd, rootfs, rev_layer)
                self._do_syncfs(rootfs, rootfs_fd)
            finally:
                if rootfs_fd:
                    os.close(rootfs_fd)

        if extract_only:
            return

        if self.user:
            values["RUN_DIRECTORY"] = os.environ.get("XDG_RUNTIME_DIR", "/run/user/%s" % (os.getuid()))
            values["STATE_DIRECTORY"] = "%s/.data" % HOME
        else:
            values["RUN_DIRECTORY"] = "/run"
            values["STATE_DIRECTORY"] = "/var/lib"

        # When installing a new system container, set values in this order:
        #
        # 1) What comes from manifest.json, if present, as default value.
        # 2) What the user sets explictly as --set
        # 3) Values for DESTDIR and NAME
        manifest_file = os.path.join(exports, "manifest.json")
        if os.path.exists(manifest_file):
            with open(manifest_file, "r") as f:
                try:
                    manifest = json.loads(f.read())
                except ValueError:
                    raise ValueError("Invalid manifest.json file in image: {}.".format(img))
                if "defaultValues" in manifest:
                    for key, val in manifest["defaultValues"].items():
                        if key not in values:
                            values[key] = val

        if self.args.setvalues is not None:
            for i in self.args.setvalues:
                split = i.find("=")
                if split < 0:
                    raise ValueError("Invalid value '%s'.  Expected form NAME=VALUE" % i)
                key, val = i[:split], i[split+1:]
                values[key] = val

        values["DESTDIR"] = destination
        values["NAME"] = name
        values["EXEC_START"], values["EXEC_STOP"] = self._generate_systemd_startstop_directives(name)
        values["HOST_UID"] = os.getuid()
        values["HOST_GID"] = os.getgid()

        def _write_template(inputfilename, data, values, destination):
            try:
                os.makedirs(os.path.dirname(destination))
            except OSError:
                pass
            with open(destination, "w") as outfile:
                template = Template(data)
                result = template.safe_substitute(values)
                missing = {"".join(x) for x in template.pattern.findall(data) if "".join(x) not in values} # pylint: disable=no-member
                if len(missing):
                    raise ValueError("The template file '%s' still contains unreplaced values for: %s" % \
                                     (inputfilename, ", ".join(missing)))
                outfile.write(result)

        src = os.path.join(exports, "config.json")
        destination_path = os.path.join(destination, "config.json")
        if os.path.exists(src):
            shutil.copyfile(src, destination_path)
        elif os.path.exists(src + ".template"):
            with open(src + ".template", 'r') as infile:
                _write_template(src + ".template", infile.read(), values, destination_path)
        else:
            self._generate_default_oci_configuration(destination)

        if remote_path:
            with open(destination_path, 'r') as config_file:
                try:
                    config = json.loads(config_file.read())
                except ValueError:
                    raise ValueError("Invalid config.json file in given remote location: {}.".format(destination_path))
                config['root']['path'] = remote_rootfs
            with open(destination_path, 'w') as config_file:
                config_file.write(json.dumps(config, indent=4))

        # When upgrading, stop the service and remove previously installed
        # tmpfiles, before restarting the service.
        if upgrade:
            if was_service_active:
                self._systemctl_command("stop", name)
            if os.path.exists(tmpfilesout):
                try:
                    self._systemd_tmpfiles("--remove", tmpfilesout)
                except subprocess.CalledProcessError:
                    pass

        missing_bind_paths = self._check_oci_configuration_file(destination_path, remote_path)

        image_manifest = self._image_manifest(repo, rev)
        image_id = rev
        if image_manifest:
            image_manifest = json.loads(image_manifest)
            if 'Digest' in image_manifest:
                image_id = image_manifest['Digest'].replace("sha256:", "")

        with open(os.path.join(destination, "info"), 'w') as info_file:
            info = {"image" : img,
                    "revision" : image_id,
                    "ostree-commit": rev,
                    'created' : calendar.timegm(time.gmtime()),
                    "values" : values,
                    "remote" : remote}
            info_file.write(json.dumps(info, indent=4))

        if os.path.exists(unitfile):
            with open(unitfile, 'r') as infile:
                systemd_template = infile.read()
        else:
            systemd_template = SYSTEMD_UNIT_FILE_DEFAULT_TEMPLATE

        if os.path.exists(tmpfiles):
            with open(tmpfiles, 'r') as infile:
                tmpfiles_template = infile.read()
        else:
            tmpfiles_template = SystemContainers._generate_tmpfiles_data(missing_bind_paths, values["STATE_DIRECTORY"])

        _write_template(unitfile, systemd_template, values, unitfileout)
        shutil.copyfile(unitfileout, os.path.join(destination, "%s.service" % name))
        if (tmpfiles_template):
            _write_template(unitfile, tmpfiles_template, values, tmpfilesout)
            shutil.copyfile(tmpfilesout, os.path.join(destination, "tmpfiles-%s.conf" % name))

        sym = "%s/%s" % (self._get_system_checkout_path(), name)
        if os.path.exists(sym):
            os.unlink(sym)
        os.symlink(destination, sym)

        self._systemctl_command("daemon-reload")
        if (tmpfiles_template):
            self._systemd_tmpfiles("--create", tmpfilesout)

        if not upgrade:
            self._systemctl_command("enable", name)
        elif was_service_active:
            self._systemctl_command("start", name)

    def _get_system_checkout_path(self):
        if os.environ.get("ATOMIC_OSTREE_CHECKOUT_PATH"):
            return os.environ.get("ATOMIC_OSTREE_CHECKOUT_PATH")
        if self.get_atomic_config_item(["checkout_path"]):
            return self.get_atomic_config_item(["checkout_path"])
        if self.user:
            return ATOMIC_VAR_USER
        else:
            return ATOMIC_VAR

    def get_ostree_repo_location(self):
        if self.user:
            return "%s/.containers/repo" % HOME
        else:
            return os.environ.get("ATOMIC_OSTREE_REPO") or \
                self.get_atomic_config_item(["ostree_repository"]) or \
                "/ostree/repo"

    def _get_ostree_repo(self):
        if not OSTREE_PRESENT:
            return None

        repo_location = self.get_ostree_repo_location()
        repo = OSTree.Repo.new(Gio.File.new_for_path(repo_location))

        # If the repository doesn't exist at the specified location, create it
        if not os.path.exists(os.path.join(repo_location, "config")):
            os.makedirs(repo_location)
            if self.user:
                repo.create(OSTree.RepoMode.BARE_USER)
            else:
                repo.create(OSTree.RepoMode.BARE)

        repo.open(None)
        return repo

    def version(self, image):
        image_inspect = self.inspect_system_image(image)
        if image_inspect:
            return [image_inspect]
        return None

    def update(self, name):
        repo = self._get_ostree_repo()
        if not repo:
            raise ValueError("Cannot find a configured OSTree repo")

        path = os.path.join(self._get_system_checkout_path(), name)
        with open(os.path.join(path, "info"), 'r') as info_file:
            info = json.loads(info_file.read())
            self.args.remote = info['remote']
            if self.args.remote:
                util.write_out("%s a container with a remote rootfs. Only changes to config will be applied." % ("Rolling back" if self.args.rollback else "Updating"))

        if self.args.rollback:
            if self.args.setvalues is not None:
                raise ValueError("Error: --set cannot be used when rolling back a container")
            self.rollback(name)
            return

        next_deployment = 0
        if os.path.realpath(path).endswith(".0"):
            next_deployment = 1

        with open(os.path.join(self._get_system_checkout_path(), name, "info"), "r") as info_file:
            info = json.loads(info_file.read())

        image = info["image"]
        values = info["values"]
        revision = info["revision"] if "revision" in info else None

        if revision and self.args.setvalues is None:
            image_inspect = self.inspect_system_image(image)
            if image_inspect:
                if image_inspect['ImageId'] == revision:
                    # Nothing to do
                    util.write_out("Latest version already installed.")
                    return

        if os.path.exists("%s/%s.%d" % (self._get_system_checkout_path(), name, next_deployment)):
            shutil.rmtree("%s/%s.%d" % (self._get_system_checkout_path(), name, next_deployment))

        self._checkout(repo, name, image, next_deployment, True, values, remote=self.args.remote)

    def rollback(self, name):
        path = os.path.join(self._get_system_checkout_path(), name)
        destination = "%s.%d" % (path, (1 if os.path.realpath(path).endswith(".0") else 0))
        if not os.path.exists(destination):
            raise ValueError("Error: Cannot find a previous deployment to rollback located at %s" % destination)

        was_service_active = self._is_service_active(name)
        unitfileout, tmpfilesout = self._get_systemd_destination_files(name)
        unitfile = os.path.join(destination, "%s.service" % name)
        tmpfiles = os.path.join(destination, "tmpfiles-%s.conf" % name)

        if not os.path.exists(unitfile):
            raise ValueError("Error: Cannot find systemd service file for previous version. "
                             "The previous checkout at %s may be corrupted." % destination)

        util.write_out("Rolling back container {} to the checkout at {}".format(name, destination))
        if was_service_active:
            self._systemctl_command("stop", name)

        if os.path.exists(tmpfilesout):
            try:
                self._systemd_tmpfiles("--remove", tmpfilesout)
            except subprocess.CalledProcessError:
                pass
            os.unlink(tmpfilesout)

        if os.path.exists(unitfileout):
            os.unlink(unitfileout)

        shutil.copyfile(unitfile, unitfileout)
        if (os.path.exists(tmpfiles)):
            shutil.copyfile(tmpfiles, tmpfilesout)

        os.unlink(path)
        os.symlink(destination, path)
        self._systemctl_command("daemon-reload")
        if (os.path.exists(tmpfiles)):
            self._systemd_tmpfiles("--create", tmpfilesout)

        if was_service_active:
            self._systemctl_command("start", name)

    def get_container_runtime_info(self, container):

        if self._is_service_active(container):
            return {'status' : "running"}
        elif self._is_service_failed(container):
            return {'status' : "failed"}
        else:
            # The container is newly created or stopped, and can be started with 'systemctl start'
            return {'status' : "inactive"}

    def get_containers(self, containers=None):
        checkouts = self._get_system_checkout_path()
        if not os.path.exists(checkouts):
            return []
        ret = []
        if containers is None:
            containers = os.listdir(checkouts)
        for x in containers:
            fullpath = os.path.join(checkouts, x)
            if not os.path.islink(fullpath):
                continue

            with open(os.path.join(fullpath, "info"), "r") as info_file:
                info = json.load(info_file)
                revision = info["revision"] if "revision" in info else ""
                created = info["created"] if "created" in info else 0
                image = info["image"] if "image" in info else ""

            with open(os.path.join(fullpath, "config.json"), "r") as config_file:
                config = json.load(config_file)
                command = u' '.join(config["process"]["args"])

            container = {'Image' : image, 'ImageID' : revision, 'Id' : x, 'Created' : created, 'Names' : [x],
                         'Command' : command, 'Type' : 'system'}
            ret.append(container)
        return ret

    def get_template_variables(self, image):
        repo = self._get_ostree_repo()
        _, commit_rev = self._resolve_image(repo, image)
        if not commit_rev:
            return

        manifest = self._image_manifest(repo, commit_rev)
        layers = SystemContainers.get_layers_from_manifest(json.loads(manifest))
        templates = {}
        manifest_template = None
        for i in layers:
            layer = i.replace("sha256:", "")
            commit = repo.read_commit(repo.resolve_rev("%s%s" % (OSTREE_OCIIMAGE_PREFIX, layer), True)[1])[1]
            exports = commit.get_root().get_child("exports")
            if not exports.query_exists():
                continue

            children = exports.enumerate_children("", Gio.FileQueryInfoFlags.NONE, None)
            for child in reversed(list(children)):
                name = child.get_name()
                if name == "manifest.json":
                    manifest_template = exports.get_child(name).read()

                if name.endswith(".template"):
                    if name.startswith(".wh"):
                        name = name[4:]
                        templates.pop(name, None)
                    else:
                        templates[name] = exports.get_child(name).read()

        variables = {}
        for v in templates.values():
            fd = v.get_fd()
            with os.fdopen(fd) as f:
                data = f.read()
                template = Template(data)
                for variable in ["".join(x) for x in template.pattern.findall(data)]: # pylint: disable=no-member
                    if variable not in TEMPLATE_FORCED_VARIABLES:
                        variables[variable] = variable

        variables_with_default = {}
        if manifest_template:
            fd = manifest_template.get_fd()
            with os.fdopen(fd) as f:
                try:
                    data = json.loads(f.read())
                except ValueError:
                    raise ValueError("Invalid manifest.json file in image: {}.".format(image))
                for variable in data['defaultValues']:
                    variables_with_default[variable] = data['defaultValues'][variable]

        # Also include variables that are set by the OS
        # but can be overriden by --set
        for variable in TEMPLATE_OVERRIDABLE_VARIABLES:
            variables_with_default[variable] = "{SET_BY_OS}"

        variables_to_set = {}
        for variable in variables:
            if variable not in variables_with_default:
                variables_to_set[variable] = "{DEF_VALUE}"

        return variables_with_default, variables_to_set

    def delete_image(self, image):
        repo = self._get_ostree_repo()
        if not repo:
            return
        imagebranch, commit_rev = self._resolve_image(repo, image)
        if not commit_rev:
            return
        ref = OSTree.parse_refspec(imagebranch)
        repo.set_ref_immediate(ref[1], ref[2], None)

    def inspect_system_image(self, image):
        repo = self._get_ostree_repo()
        if not repo:
            return None
        return self._inspect_system_branch(repo, image)

    def _inspect_system_branch(self, repo, imagebranch):
        if imagebranch.startswith(OSTREE_OCIIMAGE_PREFIX):
            commit_rev = repo.resolve_rev(imagebranch, False)[1]
        else:
            _, commit_rev = self._resolve_image(repo, imagebranch)
            if commit_rev is None:
                raise ValueError("Image %s not found" % imagebranch)
        commit = repo.load_commit(commit_rev)[1]

        branch_id = SystemContainers._decode_from_ostree_ref(imagebranch.replace(OSTREE_OCIIMAGE_PREFIX, ""))
        tag = ":".join(branch_id.rsplit(':', 1))
        timestamp = OSTree.commit_get_timestamp(commit)
        labels = {}

        manifest = self._image_manifest(repo, commit_rev)
        if len(branch_id) == 64:
            image_id = branch_id
            tag = "<none>"
        else:
            image_id = commit_rev

        if manifest:
            manifest = json.loads(manifest)
            if 'Labels' in manifest:
                labels = manifest['Labels']

            if 'Digest' in manifest:
                image_id = manifest['Digest'].replace("sha256:", "")

        if self.user:
            image_type = "user"
        else:
            image_type = "system"

        return {'Id' : image_id, 'Version' : tag, 'ImageId' : image_id, 'RepoTags' : [tag], 'Names' : [],
                'Created': timestamp, 'ImageType' : image_type, 'Labels' : labels, 'OSTree-rev' : commit_rev}

    def get_system_images(self, get_all=False, repo=None):
        if repo is None:
            repo = self._get_ostree_repo()
            if repo is None:
                return []
        revs = [x for x in repo.list_refs()[1] if x.startswith(OSTREE_OCIIMAGE_PREFIX) \
                and (get_all or len(x) != len(OSTREE_OCIIMAGE_PREFIX) + 64)]

        return [self._inspect_system_branch(repo, x) for x in revs]

    def _is_service_active(self, name):
        try:
            return self._systemctl_command("is-active", name, quiet=True).replace("\n", "") == "active"
        except subprocess.CalledProcessError:
            return False

    def _is_service_failed(self, name):
        try:
            is_failed = self._systemctl_command("is-failed", name, quiet=True).replace("\n", "")
        except subprocess.CalledProcessError as e:
            is_failed = e.output.decode('utf-8')
            if is_failed.replace("\n", "") != "inactive":
                return True

        if is_failed == "failed":
            return True
        elif is_failed == "active":
            return False
        else:
            # in case of "inactive", could be a stopped container or failed process
            try:
                status = self._systemctl_command("status", name, quiet=True)
            except subprocess.CalledProcessError as e:
                status = e.output.decode('utf-8')
            if 'FAILURE' in status:
                return True
            else:
                return False

    def start_service(self, name):
        try:
            self._systemctl_command("start", name)
        except subprocess.CalledProcessError as e:
            raise ValueError(e.output)

    def stop_service(self, name):
        try:
            self._systemctl_command("stop", name)
        except subprocess.CalledProcessError as e:
            raise ValueError(e.output)

    def _systemd_tmpfiles(self, command, name):
        cmd = ["systemd-tmpfiles"] + [command, name]
        util.write_out(" ".join(cmd))
        if not self.display:
            util.check_call(cmd)

    def _systemctl_command(self, command, name=None, quiet=False):
        cmd = ["systemctl"]
        if self.user:
            cmd.append("--user")
        cmd.append(command)
        if name:
            cmd.append(name)
        if not quiet:
            util.write_out(" ".join(cmd))
        if not self.display:
            return util.check_output(cmd, stderr=DEVNULL).decode('utf-8')
        return None

    def get_checkout(self, name):
        if len(name) == 0:
            raise ValueError("Invalid container name")
        path = "%s/%s" % (self._get_system_checkout_path(), name)
        if os.path.exists(path):
            return path
        else:
            return None

    def uninstall(self, name):
        unitfileout, tmpfilesout = self._get_systemd_destination_files(name)

        try:
            self._systemctl_command("stop", name)
        except subprocess.CalledProcessError:
            pass
        try:
            self._systemctl_command("disable", name)
        except subprocess.CalledProcessError:
            pass

        if os.path.exists(tmpfilesout):
            try:
                self._systemd_tmpfiles("--remove", tmpfilesout)
            except subprocess.CalledProcessError:
                pass
            os.unlink(tmpfilesout)

        if os.path.lexists("%s/%s" % (self._get_system_checkout_path(), name)):
            os.unlink("%s/%s" % (self._get_system_checkout_path(), name))
        for deploy in ["0", "1"]:
            if os.path.exists("%s/%s.%s" % (self._get_system_checkout_path(), name, deploy)):
                shutil.rmtree("%s/%s.%s" % (self._get_system_checkout_path(), name, deploy))

        if os.path.exists(unitfileout):
            os.unlink(unitfileout)

    def prune_ostree_images(self):
        repo = self._get_ostree_repo()
        if not repo:
            return
        refs = {}
        app_refs = []

        for i in repo.list_refs()[1]:
            if i.startswith(OSTREE_OCIIMAGE_PREFIX):
                if len(i) == len(OSTREE_OCIIMAGE_PREFIX) + 64:
                    refs[i] = False
                else:
                    invalid_encoding = False
                    for c in i.replace(OSTREE_OCIIMAGE_PREFIX, ""):
                        if not str.isalnum(str(c)) and c not in '.-_':
                            invalid_encoding = True
                            break
                    if invalid_encoding:
                        refs[i] = False
                    else:
                        app_refs.append(i)

        def visit(rev):
            manifest = self._image_manifest(repo, repo.resolve_rev(rev, True)[1])
            if not manifest:
                return
            for layer in SystemContainers.get_layers_from_manifest(json.loads(manifest)):
                refs[OSTREE_OCIIMAGE_PREFIX + layer.replace("sha256:", "")] = True

        for app in app_refs:
            visit(app)

        for k, v in refs.items():
            if not v:
                ref = OSTree.parse_refspec(k)
                util.write_out("Deleting %s" % k)
                repo.set_ref_immediate(ref[1], ref[2], None)

    @staticmethod
    def get_default_system_name(image):
        image = image.replace("oci:", "").replace("docker:", "")
        _, image, tag = SystemContainers._parse_imagename(image)
        name = image.split("/")[-1]
        if tag != "latest":
            name = "%s-%s" % (name, tag)

        return name

    @staticmethod
    def _parse_imagename(imagename):
        sep = imagename.find("/")
        reg, image = imagename[:sep], imagename[sep + 1:]
        if '.' not in reg:
            # if the registry doesn't look like a domain, consider it as the
            # image prefix
            reg = ""
            image = imagename
        sep = image.find(":")
        if sep > 0:
            return reg, image[:sep], image[sep + 1:]
        else:
            return reg, image, "latest"

    def _convert_to_skopeo(self, image):
        insecure = "http:" in image

        for i in ["oci:", "http:", "https:"]:
            image = image.replace(i, "")

        with AtomicDocker() as client:
            fqn_image = util.find_remote_image(client, image) or image
            if insecure:
                return ["--insecure"], "docker://" + fqn_image
            else:
                return [], "docker://" + fqn_image

    def _skopeo_get_manifest(self, image):
        args, img = self._convert_to_skopeo(image)
        return util.skopeo_inspect(img, args)

    def _skopeo_get_layers(self, image, layers):
        args, img = self._convert_to_skopeo(image)
        return util.skopeo_layers(img, args, layers)

    def _image_manifest(self, repo, rev):
        return SystemContainers._get_commit_metadata(repo, rev, "docker.manifest")

    def get_manifest(self, image, remote=False):
        repo = self._get_ostree_repo()
        if not repo:
            return None

        if remote:
            return self._skopeo_get_manifest(image)

        imagebranch = SystemContainers._get_ostree_image_branch(image)
        commit_rev = repo.resolve_rev(imagebranch, True)
        if not commit_rev[1]:
            return None
        return self._image_manifest(repo, commit_rev[1])

    @staticmethod
    def get_layers_from_manifest(manifest):
        if isinstance(manifest, str):
            manifest = json.loads(manifest)

        fs_layers = manifest.get("fsLayers")
        if fs_layers:
            layers = list(i["blobSum"] for i in fs_layers)
            layers.reverse()
        else:
            layers = manifest.get("Layers")
        return layers

    @staticmethod
    def _import_layers_into_ostree(repo, imagebranch, manifest, layers):
        repo.prepare_transaction()
        for layer, tar in layers.items():
            mtree = OSTree.MutableTree()
            def filter_func(*args):
                info = args[2]
                if info.get_file_type() == Gio.FileType.DIRECTORY:
                    info.set_attribute_uint32("unix::mode", info.get_attribute_uint32("unix::mode") | stat.S_IWUSR)
                return OSTree.RepoCommitFilterResult.ALLOW

            modifier = OSTree.RepoCommitModifier.new(0, filter_func, None)

            metav = GLib.Variant("a{sv}", {'docker.layer': GLib.Variant('s', layer)})

            imported = False
            try:
                repo.write_archive_to_mtree(Gio.File.new_for_path(tar), mtree, modifier, True)
                root = repo.write_mtree(mtree)[1]
                csum = repo.write_commit(None, "", None, metav, root)[1]
                imported = True
            except GLib.GError as e:  #pylint: disable=catching-non-exception
                # libarchive which is used internally by OSTree to import a tarball doesn't support correctly
                # files with xattrs.  If that happens, extract the tarball and import the directory.
                if e.domain != "g-io-error-quark":  # pylint: disable=no-member
                    raise e  #pylint: disable=raising-non-exception

            if not imported:
                try:
                    temp_dir = tempfile.mkdtemp()
                    with tarfile.open(tar, 'r') as t:
                        t.extractall(temp_dir)
                    repo.write_directory_to_mtree(Gio.File.new_for_path(temp_dir), mtree, modifier)
                    root = repo.write_mtree(mtree)[1]
                    csum = repo.write_commit(None, "", None, metav, root)[1]
                finally:
                    shutil.rmtree(temp_dir)

            root = repo.write_mtree(mtree)[1]
            csum = repo.write_commit(None, "", None, metav, root)[1]
            repo.transaction_set_ref(None, "%s%s" % (OSTREE_OCIIMAGE_PREFIX, layer), csum)

        # create a $OSTREE_OCIIMAGE_PREFIX$image-$tag branch
        if not isinstance(manifest, str):
            manifest = json.dumps(manifest)

        metadata = GLib.Variant("a{sv}", {'docker.manifest': GLib.Variant('s', manifest)})
        mtree = OSTree.MutableTree()
        file_info = Gio.FileInfo()
        file_info.set_attribute_uint32("unix::uid", 0)
        file_info.set_attribute_uint32("unix::gid", 0)
        file_info.set_attribute_uint32("unix::mode", 0o755 | stat.S_IFDIR)

        dirmeta = OSTree.create_directory_metadata(file_info, None)
        csum_dirmeta = repo.write_metadata(OSTree.ObjectType.DIR_META, None, dirmeta)[1]
        mtree.set_metadata_checksum(OSTree.checksum_from_bytes(csum_dirmeta))

        root = repo.write_mtree(mtree)[1]
        csum = repo.write_commit(None, "", None, metadata, root)[1]
        repo.transaction_set_ref(None, imagebranch, csum)

        repo.commit_transaction(None)

    def _pull_docker_image(self, repo, image):
        with tempfile.NamedTemporaryFile(mode="w") as temptar:
            util.check_call(["docker", "save", "-o", temptar.name, image])
            return self._pull_docker_tar(repo, temptar.name)

    def _pull_docker_tar(self, repo, image):
        temp_dir = tempfile.mkdtemp()
        try:
            with tarfile.open(image, 'r') as t:
                t.extractall(temp_dir)
                manifest_file = os.path.join(temp_dir, "manifest.json")
                if os.path.exists(manifest_file):
                    manifest = ""
                    with open(manifest_file, 'r') as mfile:
                        manifest = mfile.read()
                    for m in json.loads(manifest):
                        if "Config" in m:
                            config_file = os.path.join(temp_dir, m["Config"])
                            with open(config_file, 'r') as config:
                                config = json.loads(config.read())
                                labels = config['config']['Labels']
                        imagename = m["RepoTags"][0]
                        imagebranch = "%s%s" % (OSTREE_OCIIMAGE_PREFIX, SystemContainers._encode_to_ostree_ref(imagename))
                        input_layers = m["Layers"]
                        self._pull_dockertar_layers(repo, imagebranch, temp_dir, input_layers, labels=labels)
                else:
                    repositories = ""
                    repositories_file = os.path.join(temp_dir, "repositories")
                    with open(repositories_file, 'r') as rfile:
                        repositories = rfile.read()
                    imagename = list(json.loads(repositories).keys())[0]
                    imagebranch = "%s%s" % (OSTREE_OCIIMAGE_PREFIX, SystemContainers._encode_to_ostree_ref(imagename))
                    input_layers = []
                    for name in os.listdir(temp_dir):
                        if name == "repositories":
                            continue
                        input_layers.append(name + "/layer.tar")
                    self._pull_dockertar_layers(repo, imagebranch, temp_dir, input_layers)
            return imagename
        finally:
            shutil.rmtree(temp_dir)

    def _check_system_ostree_image(self, repo, img, upgrade):
        imagebranch = img.replace("ostree:", "", 1)
        current_rev = repo.resolve_rev(imagebranch, True)
        if not upgrade and current_rev[1]:
            return False
        remote, branch = imagebranch.split(":")
        return repo.pull(remote, [branch], 0, None)

    def _check_system_oci_image(self, repo, img, upgrade):
        imagebranch = "%s%s" % (OSTREE_OCIIMAGE_PREFIX, SystemContainers._encode_to_ostree_ref(img))
        current_rev = repo.resolve_rev(imagebranch, True)
        if not upgrade and current_rev[1]:
            return False

        manifest = self._skopeo_get_manifest(img)
        layers = SystemContainers.get_layers_from_manifest(manifest)
        missing_layers = []
        for i in layers:
            layer = i.replace("sha256:", "")
            has_layer = repo.resolve_rev("%s%s" % (OSTREE_OCIIMAGE_PREFIX, layer), True)[1]
            if not has_layer:
                missing_layers.append(layer)
                util.write_out("Pulling layer %s" % layer)
        layers_dir = None
        try:
            layers_to_import = {}
            if len(missing_layers):
                layers_dir = self._skopeo_get_layers(img, missing_layers)
                for root, _, files in os.walk(layers_dir):
                    for f in files:
                        if f.endswith(".tar"):
                            layer_file = os.path.join(root, f)
                            layer = f.replace(".tar", "")
                            if not repo.resolve_rev("%s%s" % (OSTREE_OCIIMAGE_PREFIX, layer), True)[1]:
                                layers_to_import[layer] = layer_file
            SystemContainers._import_layers_into_ostree(repo, imagebranch, manifest, layers_to_import)
        finally:
            if layers_dir:
                shutil.rmtree(layers_dir)
        return True

    @staticmethod
    def _generate_tmpfiles_data(missing_bind_paths, state_directory):
        def _generate_line(x, state):
            return "%s    %s   0700 %i %i - -\n" % (state, x, os.getuid(), os.getgid())
        lines = []
        for x in missing_bind_paths:
            if os.path.commonprefix([x, state_directory]) == state_directory:
                lines.append(_generate_line(x, "d"))
            else:
                lines.append(_generate_line(x, "D"))
                lines.append(_generate_line(x, "R"))
        return "".join(lines)

    @staticmethod
    def _get_commit_metadata(repo, rev, key):
        commit = repo.load_commit(rev)[1]
        metadata = commit.get_child_value(0)
        if key not in metadata.keys():
            return None
        return metadata[key]

    def extract(self, img, destination):
        repo = self._get_ostree_repo()
        if not repo:
            return False
        return self._checkout(repo, img, img, 0, False, destination=destination, extract_only=True)

    @staticmethod
    def _encode_to_ostree_ref(name):
        def convert(x):
            return (x if str.isalnum(str(x)) or x in '.-' else "_%02X" % ord(x))

        if name.startswith("oci:"):
            name = name[len("oci:"):]
        registry, image, tag = SystemContainers._parse_imagename(name)
        if registry:
            fullname = "%s/%s:%s" % (registry, image, tag)
        else:
            fullname = "%s:%s" % (image, tag)

        ret = "".join([convert(i) for i in fullname])
        return ret

    @staticmethod
    def _decode_from_ostree_ref(name):
        try:
            l = []
            i = 0
            while i < len(name):
                if name[i] == '_':
                    l.append(str(chr(int(name[i+1:i+3], 16))))
                    i = i + 3
                else:
                    l.append(name[i])
                    i = i + 1
            return "".join(l)
        except ValueError:
            return name

    @staticmethod
    def _get_ostree_image_branch(img):
        if "ostree:" in img:
            imagebranch = img.replace("ostree:", "")
        else: # assume "oci:" image
            imagebranch = "%s%s" % (OSTREE_OCIIMAGE_PREFIX, SystemContainers._encode_to_ostree_ref(img.replace("sha256:", "")))
        return imagebranch

    def has_image(self, img):
        repo = self._get_ostree_repo()
        if not repo:
            return False
        _, rev = self._resolve_image(repo, img)
        return True if rev else False

    def _pull_dockertar_layers(self, repo, imagebranch, temp_dir, input_layers, labels=None):
        layers = {}
        next_layer = {}
        top_layer = None
        for i in input_layers:
            layer = i.replace("/layer.tar", "")
            layers[layer] = os.path.join(temp_dir, i)
            with open(os.path.join(temp_dir, layer, "json"), 'r') as f:
                json_layer = json.loads(f.read())
                parent = json_layer.get("parent")
                if not parent:
                    top_layer = layer
                next_layer[parent] = layer

        layers_map = {}
        enc = sys.getdefaultencoding()
        for k, v in layers.items():
            out = util.check_output([ATOMIC_LIBEXEC + '/dockertar-sha256-helper', v],
                                    stderr=DEVNULL)
            layers_map[k] = out.decode(enc).replace("\n", "")
        layers_ordered = []

        it = top_layer
        while it:
            layers_ordered.append(layers_map[it])
            it = next_layer.get(it)

        manifest = json.dumps({"Layers" : layers_ordered, "Labels" : labels})

        layers_to_import = {}
        for k, v in layers.items():
            layers_to_import[layers_map[k]] = v
        SystemContainers._import_layers_into_ostree(repo, imagebranch, manifest, layers_to_import)

    def validate_layer(self, layer):
        ret = []
        layer = layer.replace("sha256:", "")
        repo = self._get_ostree_repo()
        if not repo:
            return ret

        def validate_ostree_file(csum):
            _, inputfile, file_info, xattrs = repo.load_file(csum)
            # images are imported from layer tarballs, without any xattr.  Don't use xattr to compute
            # the OSTree object checksum.
            xattrs = GLib.Variant("a(ayay)", [])
            _, checksum_v = OSTree.checksum_file_from_input(file_info, xattrs, inputfile, OSTree.ObjectType.FILE)
            return OSTree.checksum_from_bytes(checksum_v)

        def traverse(it):
            def get_out_content_checksum(obj): return obj.out_content_checksum if hasattr(obj, 'out_content_checksum') else obj[1]
            def get_out_checksum(obj): return obj.out_checksum if hasattr(obj, 'out_checksum') else obj[1]
            while True:
                res = it.next()  # pylint: disable=next-method-called
                if res == OSTree.RepoCommitIterResult.DIR:
                    dir_checksum = get_out_content_checksum(it.get_dir())
                    dir_it = OSTree.RepoCommitTraverseIter()
                    dirtree = repo.load_variant(OSTree.ObjectType.DIR_TREE, dir_checksum)
                    dir_it.init_dirtree(repo, dirtree[1], OSTree.RepoCommitTraverseFlags.REPO_COMMIT_TRAVERSE_FLAG_NONE)
                    traverse(dir_it)
                elif res == OSTree.RepoCommitIterResult.FILE:
                    new_checksum = validate_ostree_file(get_out_checksum(it.get_file()))
                    if new_checksum != get_out_checksum(it.get_file()):
                        ret.append({"name" : it.get_file().out_name,
                                    "old-checksum" : it.get_file().out_checksum,
                                    "new-checksum" : new_checksum})
                elif res == OSTree.RepoCommitIterResult.ERROR:
                    raise ValueError("Internal error while validating the layer")
                elif res == OSTree.RepoCommitIterResult.END:
                    break

        current_rev = repo.resolve_rev("%s%s" % (OSTREE_OCIIMAGE_PREFIX, layer), False)[1]

        it = OSTree.RepoCommitTraverseIter()
        it.init_commit(repo, repo.load_commit(current_rev)[1], OSTree.RepoCommitTraverseFlags.REPO_COMMIT_TRAVERSE_FLAG_NONE)
        traverse(it)
        return ret
