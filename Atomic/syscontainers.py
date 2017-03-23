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
from Atomic.backends._docker_errors import NoDockerDaemon
from ctypes import cdll, CDLL
import uuid

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
ATOMIC_USR = '/usr/lib/containers/atomic'
ATOMIC_VAR_USER = "%s/.containers/atomic" % HOME
OSTREE_OCIIMAGE_PREFIX = "ociimage/"
SYSTEMD_UNIT_FILES_DEST = "/etc/systemd/system"
SYSTEMD_UNIT_FILES_DEST_USER = "%s/.config/systemd/user" % HOME
SYSTEMD_TMPFILES_DEST = "/etc/tmpfiles.d"
SYSTEMD_TMPFILES_DEST_USER = "%s/.containers/tmpfiles" % HOME
SYSTEMD_UNIT_FILES_DEST_PREFIX = "%s/usr/lib/systemd/system"
SYSTEMD_TMPFILES_DEST_PREFIX = "%s/usr/lib/tmpfiles.d"
RPM_NAME_PREFIX = "atomic-container"
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
                             "HOST_UID", "HOST_GID", "IMAGE_ID", "IMAGE_NAME"]
TEMPLATE_OVERRIDABLE_VARIABLES = ["RUN_DIRECTORY", "STATE_DIRECTORY", "UUID"]

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

    @property
    def available(self):
        return OSTREE_PRESENT

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

    @staticmethod
    def _split_set_args(setvalues):
        values = {}
        for i in setvalues:
            split = i.find("=")
            if split < 0:
                raise ValueError("Invalid value '%s'.  Expected form NAME=VALUE" % i)
            key, val = i[:split], i[split+1:]
            values[key] = val
        return values

    def _pull_image_to_ostree(self, repo, image, upgrade):
        if not repo:
            raise ValueError("Cannot find a configured OSTree repo")
        if image.startswith("ostree:") and image.count(':') > 1:
            self._check_system_ostree_image(repo, image, upgrade)
        elif image.startswith("docker:") and image.count(':') > 1:
            image = self._pull_docker_image(repo, image.replace("docker:", "", 1))
        elif image.startswith("dockertar:/"):
            tarpath = image.replace("dockertar:/", "", 1)
            image = self._pull_docker_tar(repo, tarpath, os.path.basename(tarpath).replace(".tar", ""))
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

    def _install_rpm(self, rpm_file):
        if os.path.exists("/run/ostree-booted"):
            raise ValueError("This doesn't work on Atomic Host yet")
        elif os.path.exists("/usr/bin/dnf"):
            util.check_call(["dnf", "install", "-y", rpm_file])
        else:
            util.check_call(["yum", "install", "-y", rpm_file])

    def _uninstall_rpm(self, rpm):
        if os.path.exists("/run/ostree-booted"):
            raise ValueError("This doesn't work on Atomic Host yet")
        elif os.path.exists("/usr/bin/dnf"):
            util.check_call(["dnf", "remove", "-y", rpm])
        else:
            util.check_call(["yum", "remove", "-y", rpm])

    @staticmethod
    def _find_rpm(tmp_dir):
        rpm_file = None
        if tmp_dir == None:
            return None
        for root, _, files in os.walk(os.path.join(tmp_dir, "build")):
            if rpm_file:
                break
            for f in files:
                if f.endswith('.rpm'):
                    rpm_file = os.path.join(root, f)
                    break
        return rpm_file

    def install(self, image, name):
        repo = self._get_ostree_repo()
        if not repo:
            raise ValueError("Cannot find a configured OSTree repo")

        if self.args.system and self.user:
            raise ValueError("Only root can use --system")

        accepted_system_package_values = ['auto', 'build', 'no', 'yes']
        if self.args.system_package not in accepted_system_package_values:
            raise ValueError("Invalid --system-package mode.  Accepted values: '%s'" % "', '".join(accepted_system_package_values))

        if self.get_checkout(name):
            util.write_out("%s already present" % (name))
            return

        image = self._pull_image_to_ostree(repo, image, False)
        tmp_dir = None
        try:
            if self.args.system_package == 'auto' and not self.args.system:
                self.args.system_package = 'no'
            if self.args.system_package in ['build', 'yes'] and not self.args.system:
                raise ValueError("Only --system can generate rpms")

            if self.args.system_package == 'build':
                tmp_dir = self.generate_rpm(repo, name, image, include_containers_file=True)
                if tmp_dir:
                    rpm_preinstalled = SystemContainers._find_rpm(tmp_dir)
                    # If we are only build'ing the rpm, copy it to the cwd and exit
                    destination = os.path.join(os.getcwd(), os.path.basename(rpm_preinstalled))
                    shutil.move(rpm_preinstalled, destination)
                    util.write_out("Generated rpm %s" % destination)
                return False
        finally:
            if tmp_dir:
                shutil.rmtree(tmp_dir)

        values = {}
        if self.args.setvalues is not None:
            setvalues = SystemContainers._split_set_args(self.args.setvalues)
            for k, v in setvalues.items():
                values[k] = v

        self._checkout(repo, name, image, 0, False, values=values, remote=self.args.remote, system_package=self.args.system_package)

    def _check_oci_configuration_file(self, conf_path, remote=None, include_all=False):
        with open(conf_path, 'r') as conf:
            try:
                configuration = json.loads(conf.read())
            except ValueError:
                raise ValueError("Invalid json in configuration file: {}.".format(conf_path))
        # empty file, nothing to do here
        if len(configuration) == 0:
            return []
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
                    if include_all or not os.path.exists(source):
                        missing_source_paths.append(source)
        return missing_source_paths

    def _generate_default_oci_configuration(self, destination):
        conf_path = os.path.join(destination, "config.json")

        # If runc is not installed we are not able to generate the default configuration,
        # write an empty JSON file
        if not util.runc_available():
            with open(conf_path, 'w') as conf:
                conf.write('{}')
            return

        args = [util.RUNC_PATH, 'spec']
        util.subp(args, cwd=destination)
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

        try:
            version = str(util.check_output([util.RUNC_PATH, "--version"], stderr=DEVNULL))
        except util.FileNotFound:
            version = ""
        if "version 0" in version:
            runc_commands = ["start", "kill"]
        else:
            runc_commands = ["run", "kill"]
        return ["%s %s '%s'" % (util.RUNC_PATH, command, name) for command in runc_commands]

    def _get_systemd_destination_files(self, name, prefix=None):
        if self.user:
            unitfileout = os.path.join(SYSTEMD_UNIT_FILES_DEST_USER, "%s.service" % name)
            tmpfilesout = os.path.join(SYSTEMD_TMPFILES_DEST_USER, "%s.conf" % name)
        else:
            if prefix:
                unitfileout = os.path.join(SYSTEMD_UNIT_FILES_DEST_PREFIX % prefix, "%s.service" % name)
                tmpfilesout = os.path.join(SYSTEMD_TMPFILES_DEST_PREFIX % prefix, "%s.conf" % name)
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

    def _checkout(self, repo, name, img, deployment, upgrade, values=None, destination=None, extract_only=False, remote=None, prefix=None, installed_files=None, system_package='no'):
        destination = destination or "%s/%s.%d" % (self._get_system_checkout_path(), name, deployment)
        unitfileout, tmpfilesout = self._get_systemd_destination_files(name, prefix)

        if not upgrade:
            for f in [unitfileout, tmpfilesout]:
                if os.path.exists(f):
                    raise ValueError("The file %s already exists." % f)

        try:
            return self._do_checkout(repo, name, img, upgrade, values, destination, unitfileout, tmpfilesout, extract_only, remote, prefix, installed_files=installed_files,
                                     system_package=system_package)
        except (ValueError, OSError) as e:
            try:
                if not extract_only and not upgrade:
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

    @staticmethod
    def _get_image_id_from_manifest(image_manifest):
        if 'Digest' in image_manifest:
            image_id = image_manifest['Digest']
        elif 'config' in image_manifest and 'digest' in image_manifest['config']:
            image_id = image_manifest['config']['digest']
        else:
            return None
        return SystemContainers._drop_sha256_prefix(image_id)

    # Accept both name and version Id, and return the ostree rev
    def _resolve_image(self, repo, img, allow_multiple=False):
        imagebranch = SystemContainers._get_ostree_image_branch(img)
        rev = repo.resolve_rev(imagebranch, True)[1]
        if rev:
            return [(imagebranch, rev)]

        # if we could not find an image with the specified name, check if it is the prefix
        # of an ID, and allow it only for tagged images.
        if not str.isalnum(str(img)):
            return None

        tagged_images = [i for i in self.get_system_images(get_all=True, repo=repo) if i['RepoTags']]
        matches = [i for i in tagged_images if i['ImageId'].startswith(img)]

        if len(matches) == 0:
            return None

        if len(matches) > 1 and not allow_multiple:
            # more than one match, error out
            raise ValueError("more images matching prefix `%s`" % img)

        # only one image, use it
        def get_image(i):
            repotag = i['RepoTags'][0]
            if repotag == '<none>':
                imagebranch = "%s%s" % (OSTREE_OCIIMAGE_PREFIX, i['Id'])
            else:
                imagebranch = "%s%s" % (OSTREE_OCIIMAGE_PREFIX, SystemContainers._encode_to_ostree_ref(repotag))
            return imagebranch, i['OSTree-rev']

        return [get_image(i) for i in matches]

    @staticmethod
    def _write_template(inputfilename, data, values, destination):

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

    def _should_be_installed_rpm(self, exports):
        for i in ["rpm.spec", "rpm.spec.template", "hostfs"]:
            if os.path.exists(os.path.join(exports, i)):
                return True
        return False

    def _do_checkout(self, repo, name, img, upgrade, values, destination, unitfileout, tmpfilesout, extract_only, remote, prefix=None, installed_files=None,
                     system_package='no'):
        if values is None:
            values = {}

        remote_path = self._resolve_remote_path(remote)

        imgs = self._resolve_image(repo, img)
        if imgs is None:
            raise ValueError("Image %s not found" % img)

        _, rev = imgs[0]

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
            return values

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

        if remote_path:
            if not os.path.exists(destination):
                os.makedirs(destination)
        else:
            if not os.path.exists(rootfs):
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
            return values

        if self.user:
            values["RUN_DIRECTORY"] = os.environ.get("XDG_RUNTIME_DIR", "/run/user/%s" % (os.getuid()))
            values["STATE_DIRECTORY"] = "%s/.data" % HOME
        else:
            values["RUN_DIRECTORY"] = "/run"
            values["STATE_DIRECTORY"] = "/var/lib"

        if not os.path.exists(exports):
            util.write_out("""Warning: /exports directory not found.  Default config files will be generated.
Warning: You may want to modify `%s` before starting the service""" % os.path.join(destination, "config.json"))

        if system_package == 'auto':
            system_package = "yes" if self._should_be_installed_rpm(exports) else 'no'

        # When installing a new system container, set values in this order:
        #
        # 1) What comes from manifest.json, if present, as default value.
        # 2) What the user sets explictly as --set
        # 3) Values for DESTDIR and NAME
        manifest_file = os.path.join(exports, "manifest.json")
        installed_files_template = []
        has_container_service = True
        rename_files = {}
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
                if "installedFilesTemplate" in manifest:
                    installed_files_template = manifest["installedFilesTemplate"]
                if "renameFiles" in manifest:
                    rename_files = manifest["renameFiles"]
                if "noContainerService" in manifest and manifest["noContainerService"]:
                    has_container_service = False

        image_manifest = self._image_manifest(repo, rev)
        image_id = rev
        if image_manifest:
            image_manifest = json.loads(image_manifest)
            image_id = SystemContainers._get_image_id_from_manifest(image_manifest) or image_id

        if "UUID" not in values:
            values["UUID"] = str(uuid.uuid4())
        values["DESTDIR"] = os.path.join("/", os.path.relpath(destination, prefix)) if prefix else destination
        values["NAME"] = name
        values["EXEC_START"], values["EXEC_STOP"] = self._generate_systemd_startstop_directives(name)
        values["HOST_UID"] = os.getuid()
        values["HOST_GID"] = os.getgid()
        values["IMAGE_NAME"] = img
        values["IMAGE_ID"] = image_id

        src = os.path.join(exports, "config.json")
        destination_path = os.path.join(destination, "config.json")
        if os.path.exists(src):
            shutil.copyfile(src, destination_path)
        elif os.path.exists(src + ".template"):
            with open(src + ".template", 'r') as infile:
                SystemContainers._write_template(src + ".template", infile.read(), values, destination_path)
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
            # create a symlink to the real rootfs, so that it is possible
            # to access the rootfs in the same way as in the not --remote case.
            os.symlink(remote_rootfs, os.path.join(destination, "rootfs"))

        # When upgrading, stop the service and remove previously installed
        # tmpfiles, before restarting the service.
        if has_container_service and upgrade:
            if was_service_active:
                self._systemctl_command("stop", name)
            if os.path.exists(tmpfilesout):
                try:
                    self._systemd_tmpfiles("--remove", tmpfilesout)
                except subprocess.CalledProcessError:
                    pass

        # rename_files may contain variables that need to be replaced.
        if rename_files:
            for k, v in rename_files.items():
                template = Template(v)
                try:
                    new_v = template.substitute(values)
                except KeyError as e:
                    raise ValueError("The template file 'manifest.json' still contains an unreplaced value for: '%s'" % \
                                     (str(e)))
                rename_files[k] = new_v

        missing_bind_paths = self._check_oci_configuration_file(destination_path, remote_path, True)

        # If rpm.spec or rpm.spec.template exist, copy them to the checkout directory, processing the .template version.
        if os.path.exists(os.path.join(exports, "rpm.spec.template")):
            with open(os.path.join(exports, "rpm.spec.template"), "r") as f:
                spec_content = f.read()
            SystemContainers._write_template("rpm.spec.template", spec_content, values, os.path.join(destination, "rpm.spec"))
        elif os.path.exists(os.path.join(rootfs, "rpm.spec")):
            shutil.copyfile(os.path.join(rootfs, "rpm.spec"), os.path.join(destination, "rpm.spec"))

        # let's check if we can generate an rpm from the /exports directory
        rpm_preinstalled = None
        if system_package == 'yes':
            temp_dir = tempfile.mkdtemp()
            try:
                rpm_content = os.path.join(temp_dir, "rpmroot")
                rootfs = os.path.join(rpm_content, "usr/lib/containers/atomic", name)
                os.makedirs(rootfs)
                installed_files = self._rm_add_files_to_host(None, exports, rpm_content, files_template=installed_files_template, values=values, rename_files=rename_files)
                rpm_root = self._generate_rpm_from_rootfs(destination, temp_dir, name, img, values, include_containers_file=False, installed_files=installed_files)
                rpm_preinstalled = SystemContainers._find_rpm(rpm_root)
                if rpm_preinstalled:
                    shutil.move(rpm_preinstalled, destination)
                    rpm_preinstalled = os.path.join(destination, os.path.basename(rpm_preinstalled))
            finally:
                shutil.rmtree(temp_dir)

        if rpm_preinstalled:
            new_installed_files = []
        else:
            new_installed_files = self._rm_add_files_to_host(installed_files, exports, prefix or "/", files_template=installed_files_template, values=values, rename_files=rename_files)

        try:
            rpm_installed = os.path.basename(rpm_preinstalled) if rpm_preinstalled else None
            with open(os.path.join(destination, "info"), 'w') as info_file:
                info = {"image" : img,
                        "revision" : image_id,
                        "ostree-commit": rev,
                        'created' : calendar.timegm(time.gmtime()),
                        "values" : values,
                        "has-container-service" : has_container_service,
                        "installed-files": new_installed_files,
                        "installed-files-template": installed_files_template,
                        "rename-installed-files" : rename_files,
                        "rpm-installed" : rpm_installed,
                        "remote" : remote}
                info_file.write(json.dumps(info, indent=4))
                info_file.write("\n")
        except (NameError, AttributeError, OSError) as e:
            for i in new_installed_files:
                os.remove(os.path.join(prefix or "/", os.path.relpath(i, "/")))
            raise e

        if os.path.exists(unitfile):
            with open(unitfile, 'r') as infile:
                systemd_template = infile.read()
        else:
            systemd_template = SYSTEMD_UNIT_FILE_DEFAULT_TEMPLATE

        if os.path.exists(tmpfiles):
            with open(tmpfiles, 'r') as infile:
                tmpfiles_template = infile.read()
        else:
            tmpfiles_template = SystemContainers._generate_tmpfiles_data(missing_bind_paths)

        if has_container_service:
            SystemContainers._write_template(unitfile, systemd_template, values, unitfileout)
            shutil.copyfile(unitfileout, os.path.join(prefix, destination, "%s.service" % name))
        if (tmpfiles_template):
            SystemContainers._write_template(unitfile, tmpfiles_template, values, tmpfilesout)
            shutil.copyfile(tmpfilesout, os.path.join(prefix, destination, "tmpfiles-%s.conf" % name))

        if not prefix:
            sym = "%s/%s" % (self._get_system_checkout_path(), name)
            if os.path.exists(sym):
                os.unlink(sym)
            os.symlink(destination, sym)

        # if there is no container service, delete the checked out files.  At this point files copied to the host
        # are already handled.
        if not has_container_service:
            if not remote_path:
                shutil.rmtree(os.path.join(destination, "rootfs"))
            return values

        if prefix:
            return values

        sym = "%s/%s" % (self._get_system_checkout_path(), name)
        if os.path.exists(sym):
            os.unlink(sym)
        os.symlink(destination, sym)

        if rpm_preinstalled:
            self._install_rpm(rpm_preinstalled)

        self._systemctl_command("daemon-reload")
        if (tmpfiles_template):
            self._systemd_tmpfiles("--create", tmpfilesout)

        if not upgrade:
            self._systemctl_command("enable", name)
        elif was_service_active:
            self._systemctl_command("start", name)

        return values

    def _get_preinstalled_containers_path(self):
        return ATOMIC_USR

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

    @staticmethod
    def _rm_add_files_to_host(old_installed_files, exports, prefix="/", files_template=None, values=None, rename_files=None):
        # if any file was installed on the host delete it
        if old_installed_files:
            for i in old_installed_files:
                try:
                    os.remove(i)
                except OSError:
                    pass

        if not exports:
            return []

        templates_set = set(files_template or [])

        # if there is a directory hostfs/ under exports, copy these files to the host file system.
        hostfs = os.path.join(exports, "hostfs")
        new_installed_files = []
        if os.path.exists(hostfs):
            for root, _, files in os.walk(hostfs):
                rel_root_path = os.path.relpath(root, hostfs)
                if not os.path.exists(os.path.join(prefix, rel_root_path)):
                    os.makedirs(os.path.join(prefix, rel_root_path))
                for f in files:
                    src_file = os.path.join(root, f)
                    dest_path = os.path.join(prefix, rel_root_path, f)
                    rel_dest_path = os.path.join("/", rel_root_path, f)

                    # If rename_files is set, rename the destination file
                    if rename_files and rel_dest_path in rename_files:
                        rel_dest_path = rename_files.get(rel_dest_path)
                        dest_path = os.path.join(prefix or "/", os.path.relpath(rel_dest_path, "/"))

                    if os.path.exists(dest_path):
                        for i in new_installed_files:
                            os.remove(new_installed_files)
                        raise ValueError("File %s already exists." % dest_path)

                    if rel_dest_path in templates_set:
                        with open(src_file, 'r') as src_file_obj:
                            data = src_file_obj.read()
                        SystemContainers._write_template(src_file, data, values or {}, dest_path)
                        shutil.copystat(src_file, dest_path)
                    else:
                        shutil.copy2(src_file, dest_path)

                    new_installed_files.append(rel_dest_path)
            new_installed_files.sort()  # just for an aesthetic reason in the info file output

        return new_installed_files

    def update_container(self, name, setvalues=None, rebase=None):
        if self._is_preinstalled_container(name):
            raise ValueError("Cannot update a preinstalled container")

        repo = self._get_ostree_repo()
        if not repo:
            raise ValueError("Cannot find a configured OSTree repo")

        path = os.path.join(self._get_system_checkout_path(), name)
        with open(os.path.join(path, "info"), 'r') as info_file:
            info = json.loads(info_file.read())
            self.args.remote = info['remote']
            if self.args.remote:
                util.write_out("Updating a container with a remote rootfs. Only changes to config will be applied.")

        next_deployment = 0
        if os.path.realpath(path).endswith(".0"):
            next_deployment = 1

        with open(os.path.join(self._get_system_checkout_path(), name, "info"), "r") as info_file:
            info = json.loads(info_file.read())

        image = rebase or info["image"]
        values = info["values"]
        revision = info["revision"] if "revision" in info else None
        installed_files = info["installed-files"] if "installed-files" in info else None
        rpm_installed = info["rpm-installed"] if "rpm-installed" in info else None

        # Check if the image id or the configuration for the container has
        # changed before upgrading it.
        revision_changed = True
        if revision:
            image_inspect = self.inspect_system_image(image)
            if image_inspect:
                if image_inspect['ImageId'] == revision:
                    revision_changed = False

        # Override values with anything coming from setvalues and while at it
        # check if anything was changed.
        values_changed = False
        if setvalues:
            for k, v in SystemContainers._split_set_args(setvalues).items():
                old = values.get(k)
                values[k] = v
                if old != v:
                    values_changed = True

        if not revision_changed and not values_changed:
            # Nothing to do
            util.write_out("Latest version already installed.")
            return

        system_package = 'yes' if rpm_installed else 'no'
        self._checkout(repo, name, image, next_deployment, True, values, remote=self.args.remote, installed_files=installed_files, system_package=system_package)
        return

    def rollback(self, name):
        path = os.path.join(self._get_system_checkout_path(), name)
        destination = "%s.%d" % (path, (1 if os.path.realpath(path).endswith(".0") else 0))
        if not os.path.exists(destination):
            raise ValueError("Error: Cannot find a previous deployment to rollback located at %s" % destination)

        installed_files = None
        rename_files = None
        with open(os.path.join(self._get_system_checkout_path(), name, "info"), "r") as info_file:
            info = json.loads(info_file.read())
            rpm_installed = info["rpm-installed"] if "rpm-installed" in info else None
            installed_files = info["installed-files"] if "installed-files" in info and rpm_installed is None else None
            installed_files_template = info["installed-files-template"] if "installed-files-template" in info and rpm_installed is None else None
            has_container_service = info["has-container-service"] if "has-container-service" in info else True
            rename_files = info["rename-installed-files"] if "rename-installed-files" in info else None

        was_service_active = has_container_service and self._is_service_active(name)
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

        if installed_files:
            self._rm_add_files_to_host(installed_files, os.path.join(destination, "rootfs/exports"), files_template=installed_files_template, rename_files=rename_files)

        os.unlink(path)
        os.symlink(destination, path)

        # reinstall the previous rpm if any.
        rpm_installed = None
        with open(os.path.join(self._get_system_checkout_path(), name, "info"), "r") as info_file:
            info = json.loads(info_file.read())
            rpm_installed = info["rpm-installed"] if "rpm-installed" in info else None

        if rpm_installed:
            self._install_rpm(os.path.join(self._get_system_checkout_path(), name, rpm_installed))

        if has_container_service:
            self._systemctl_command("daemon-reload")
        if (os.path.exists(tmpfiles)):
            self._systemd_tmpfiles("--create", tmpfilesout)

        if was_service_active:
            self._systemctl_command("start", name)

    def get_container_runtime_info(self, container):

        info_path = os.path.join(self._get_system_checkout_path(), container, "info")
        if not os.path.exists(info_path):
            info_path = os.path.join(self._get_preinstalled_containers_path(), container, "info")

        with open(info_path, "r") as info_file:
            info = json.loads(info_file.read())
            has_container_service = info["has-container-service"] if "has-container-service" in info else True

        if not has_container_service:
            return {'status' : "no service"}
        if self._is_service_active(container):
            return {'status' : "running"}
        elif self._is_service_failed(container):
            return {'status' : "failed"}
        else:
            # The container is newly created or stopped, and can be started with 'systemctl start'
            return {'status' : "inactive"}

    def _get_containers_at(self, checkouts, are_preinstalled, containers=None):
        if not checkouts or not os.path.exists(checkouts):
            return []
        ret = []
        if containers is None:
            containers = os.listdir(checkouts)
        for x in containers:
            if x[0] == ".":
                continue
            fullpath = os.path.join(checkouts, x)
            if not os.path.exists(fullpath):
                continue
            if fullpath.endswith(".0") or fullpath.endswith(".1"):
                continue

            with open(os.path.join(fullpath, "info"), "r") as info_file:
                info = json.load(info_file)
                revision = info["revision"] if "revision" in info else ""
                created = info["created"] if "created" in info else 0
                image = info["image"] if "image" in info else ""

            with open(os.path.join(fullpath, "config.json"), "r") as config_file:
                config = json.load(config_file)
                command = u' '.join(config["process"]["args"])

            runtime = "bwrap-oci" if self.user else "runc"
            container = {'Image' : image, 'ImageID' : revision, 'Id' : x, 'Created' : created, 'Names' : [x],
                         'Command' : command, 'Type' : 'system', 'Runtime' : runtime, "Preinstalled" : are_preinstalled}
            ret.append(container)
        return ret

    def get_containers(self, containers=None):
        checkouts = self._get_system_checkout_path()
        preinstalled = self._get_preinstalled_containers_path()
        return self._get_containers_at(checkouts, False, containers) + self._get_containers_at(preinstalled, True, containers)

    def get_template_variables(self, image):
        repo = self._get_ostree_repo()
        imgs = self._resolve_image(repo, image)
        if not imgs:
            return None, None
        _, commit_rev = imgs[0]
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
        imgs = self._resolve_image(repo, image, allow_multiple=True)
        if not imgs:
            return
        for imagebranch, _ in imgs:
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
            imgs = self._resolve_image(repo, imagebranch, allow_multiple=True)
            if imgs is None:
                raise ValueError("Image %s not found" % imagebranch)
            _, commit_rev = imgs[0]
        commit = repo.load_commit(commit_rev)[1]

        timestamp = OSTree.commit_get_timestamp(commit)
        branch_id = SystemContainers._decode_from_ostree_ref(imagebranch.replace(OSTREE_OCIIMAGE_PREFIX, ""))

        image_id = commit_rev
        id_ = None

        if len(branch_id) == 64:
            image_id = branch_id
            tag = "<none>"
        elif '@sha256:' in branch_id:
            id_ = branch_id
            tags = branch_id.rsplit('@sha256:', 1)
            tag = ":".join(tags)
        else:
            tag = ":".join(branch_id.rsplit(':', 1))

        labels = {}
        manifest = self._image_manifest(repo, commit_rev)
        if manifest:
            manifest = json.loads(manifest)
            if 'Labels' in manifest:
                labels = manifest['Labels']
            image_id = SystemContainers._get_image_id_from_manifest(manifest) or image_id

        if self.user:
            image_type = "user"
        else:
            image_type = "system"

        return {'Id' : id_ or image_id, 'Version' : tag, 'ImageId' : image_id, 'RepoTags' : [tag], 'Names' : [],
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
            ret = self._systemctl_command("is-active", name, quiet=True)
            return ret and ret.replace("\n", "") == "active"
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

        path = "%s/%s" % (self._get_preinstalled_containers_path(), name)
        if os.path.exists(path):
            return path

        return None

    def _is_preinstalled_container(self, name):
        path = "%s/%s" % (self._get_system_checkout_path(), name)
        if os.path.exists(path):
            return False

        path = "%s/%s" % (self._get_preinstalled_containers_path(), name)
        return os.path.exists(path)

    def uninstall(self, name):
        if self._is_preinstalled_container(name):
            self._uninstall_rpm("%s-%s" % (RPM_NAME_PREFIX, name))
            return

        if not os.path.exists(os.path.join(self._get_system_checkout_path(), name)):
            return

        with open(os.path.join(self._get_system_checkout_path(), name, "info"), "r") as info_file:
            info = json.loads(info_file.read())
            has_container_service = info["has-container-service"] if "has-container-service" in info else True
            rpm_installed = info["rpm-installed"] if "rpm-installed" in info else None

        unitfileout, tmpfilesout = self._get_systemd_destination_files(name)
        if has_container_service:
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

        checkout = self._get_system_checkout_path()
        installed_files = None
        with open(os.path.join(checkout, name,  "info"), 'r') as info_file:
            info = json.loads(info_file.read())
            installed_files = info["installed-files"] if "installed-files" in info else None
        if installed_files:
            self._rm_add_files_to_host(installed_files, None)

        if os.path.lexists("%s/%s" % (checkout, name)):
            os.unlink("%s/%s" % (checkout, name))
        for deploy in ["0", "1"]:
            if os.path.exists("%s/%s.%s" % (checkout, name, deploy)):
                shutil.rmtree("%s/%s.%s" % (checkout, name, deploy))

        if os.path.exists(unitfileout):
            os.unlink(unitfileout)

        if rpm_installed:
            self._uninstall_rpm(rpm_installed.replace(".rpm", ""))

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
        repo.prune(OSTree.RepoPruneFlags.NONE, -1)

    @staticmethod
    def get_default_system_name(image):
        if '@sha256:' in image:
            image = image.split('@sha256:')[0]
        image = image.replace("oci:", "", 1).replace("docker:", "", 1)
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

        try:
            with AtomicDocker() as client:
                image = util.find_remote_image(client, image) or image
        except NoDockerDaemon:
            pass

        if insecure:
            return ["--insecure"], "docker://" + image
        else:
            return None, "docker://" + image

    def _skopeo_get_manifest(self, image):
        args, img = self._convert_to_skopeo(image)
        return util.skopeo_inspect(img, args)

    def _skopeo_get_layers(self, image, layers):
        _, img = self._convert_to_skopeo(image)
        return util.skopeo_layers(img, [], layers)

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
        elif "layers" in manifest:
            layers = [x['digest'] for x in manifest.get("layers")]
        else:
            layers = manifest.get("Layers")
        return layers

    def _import_layers_into_ostree(self, repo, imagebranch, manifest, layers):
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
                checkout = self._get_system_checkout_path()
                destdir = checkout if os.path.exists(checkout) else None
                try:
                    temp_dir = tempfile.mkdtemp(prefix=".", dir=destdir)
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
            return self._pull_docker_tar(repo, temptar.name, image)

    def _pull_docker_tar(self, repo, tarpath, image):
        temp_dir = tempfile.mkdtemp()
        try:
            with tarfile.open(tarpath, 'r') as t:
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
                        imagename = m["RepoTags"][0] if m.get("RepoTags") else image
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
        try:
            manifest = self._skopeo_get_manifest(img)
        except ValueError:
            raise ValueError("Unable to find {}".format(img))
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
            self._import_layers_into_ostree(repo, imagebranch, manifest, layers_to_import)
        finally:
            if layers_dir:
                shutil.rmtree(layers_dir)
        return True

    @staticmethod
    def _generate_tmpfiles_data(missing_bind_paths):
        def _generate_line(x, state):
            return "%s    %s   0700 %i %i - -\n" % (state, x, os.getuid(), os.getgid())
        lines = []
        for x in missing_bind_paths:
            lines.append(_generate_line(x, "d"))
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
        self._checkout(repo, img, img, 0, False, destination=destination, extract_only=True)

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
    def _drop_sha256_prefix(img):
        if img.startswith("sha256:"):
            img = img.replace("sha256:", "", 1)
        return img

    @staticmethod
    def _get_ostree_image_branch(img):
        if "ostree:" in img:
            imagebranch = img.replace("ostree:", "")
        else: # assume "oci:" image
            img = SystemContainers._drop_sha256_prefix(img)
            imagebranch = "%s%s" % (OSTREE_OCIIMAGE_PREFIX, SystemContainers._encode_to_ostree_ref(img))
        return imagebranch

    def has_image(self, img):
        repo = self._get_ostree_repo()
        if not repo:
            return False
        return bool(self._resolve_image(repo, img, allow_multiple=True))

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
        self._import_layers_into_ostree(repo, imagebranch, manifest, layers_to_import)

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

    def generate_rpm(self, repo, name, image, include_containers_file=True):
        temp_dir = tempfile.mkdtemp()
        rpm_content = os.path.join(temp_dir, "rpmroot")
        rootfs = os.path.join(rpm_content, "usr/lib/containers/atomic", name)
        os.makedirs(rootfs)
        success = False
        try:
            values = self._checkout(repo, name, image, 0, False, destination=rootfs, prefix=rpm_content)
            if self.display:
                return None
            ret = self._generate_rpm_from_rootfs(rootfs, temp_dir, name, image, values, include_containers_file)
            if ret:
                success = True
            return ret
        finally:
            if not success:
                shutil.rmtree(temp_dir)

    def _generate_rpm_from_rootfs(self, rootfs, temp_dir, name, image, values, include_containers_file, installed_files=None):
        image_inspect = self.inspect_system_image(image)
        rpm_content = os.path.join(temp_dir, "rpmroot")
        spec_file = os.path.join(temp_dir, "container.spec")

        included_rpm = os.path.join(rootfs, "rootfs", "exports", "container.rpm")
        if os.path.exists(included_rpm):
            return included_rpm

        if installed_files is None:
            with open(os.path.join(rootfs, "info"), "r") as info_file:
                info = json.loads(info_file.read())
                installed_files = info["installed-files"] if "installed-files" in info else None

        labels = {k.lower() : v for k, v in image_inspect.get('Labels', {}).items()}
        summary = labels.get('summary', name)
        version = labels.get("version", '1')
        release = labels.get("release", image_inspect["ImageId"])
        license_ = labels.get("license", "GPLv2")
        url = labels.get("url")
        source0 = labels.get("source0")
        requires = labels.get("requires")
        provides = labels.get("provides")
        conflicts = labels.get("conflicts")
        description = labels.get("description")

        image_id = values["IMAGE_ID"]

        if os.path.exists(os.path.join(rootfs, "rpm.spec")):
            with open(os.path.join(rootfs, "rpm.spec"), "r") as f:
                spec_content = f.read()
        else:
            spec_content = self._generate_spec_file(rpm_content, name, summary, license_, image_id, version=version,
                                                    release=release, url=url, source0=source0, requires=requires,
                                                    provides=provides, conflicts=conflicts, description=description,
                                                    installed_files=installed_files, include_containers_file=include_containers_file)

        with open(spec_file, "w") as f:
            f.write(spec_content)

        cwd = os.getcwd()
        result_dir = os.path.join(temp_dir, "build")
        if not os.path.exists(result_dir):
            os.makedirs(result_dir)
        cmd = ["rpmbuild", "--noclean", "-bb", spec_file,
               "--define", "_sourcedir %s" % temp_dir,
               "--define", "_specdir %s" % temp_dir,
               "--define", "_builddir %s" % temp_dir,
               "--define", "_srcrpmdir %s" % cwd,
               "--define", "_rpmdir %s" % result_dir,
               "--build-in-place",
               "--buildroot=%s" % rpm_content]
        util.write_out(" ".join(cmd))
        if not self.display:
            util.check_call(cmd)
        return temp_dir

    def _generate_spec_file(self, destdir, name, summary, license_, image_id, version="1.0", release="1", url=None,
                            source0=None, requires=None, conflicts=None, provides=None, description=None,
                            installed_files=None, include_containers_file=True):
        spec = "%global __requires_exclude_from ^.*$\n"
        spec = spec + "%global __provides_exclude_from ^.*$\n"
        spec = spec + "%define _unpackaged_files_terminate_build 0\n"

        fields = {"Name" : "%s-%s" % (RPM_NAME_PREFIX, name), "Version" : version, "Release" : release, "Summary" : summary,
                  "License" : license_, "URL" : url, "Source0" : source0, "Requires" : requires,
                  "Provides" : provides, "Conflicts" : conflicts}
        for k, v in fields.items():
            if v is not None:
                spec = spec + "%s:\t%s\n" % (k, v)

        spec = spec + ("\n%%description\nImage ID: %s\n" % image_id)
        if description:
            spec = spec + "%s\n" % description

        spec = spec + "\n%files\n"
        for root, _, files in os.walk(os.path.join(destdir, "etc")):
            rel_path = os.path.relpath(root, destdir)
            for f in files:
                spec += "%config \"%s\"\n" % os.path.join("/", rel_path, f)

        if include_containers_file:
            spec += "/usr/lib/containers/atomic/%s\n" % name
        for root, _, files in os.walk(os.path.join(destdir, "usr/lib/systemd/system")):
            for f in files:
                spec = spec + "/usr/lib/systemd/system/%s\n" % f
        for root, _, files in os.walk(os.path.join(destdir, "usr/lib/tmpfiles.d")):
            for f in files:
                spec = spec + "/usr/lib/tmpfiles.d/%s\n" % f
        if installed_files:
            for i in installed_files:
                spec = spec + "%s\n" % i

        return spec
