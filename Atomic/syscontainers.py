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

ATOMIC_LIBEXEC = os.environ.get('ATOMIC_LIBEXEC', '/usr/libexec/atomic')

OSTREE_OCIIMAGE_PREFIX = "ociimage/"
SYSTEMD_UNIT_FILES_DEST = "/etc/systemd/system"
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

class SystemContainers(object):

    def __init__(self):
        self.atomic_config = util.get_atomic_config()
        self.backend = None
        self.user = None
        self.args = None
        self.setvalues = None

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
        OSTREE_SAFE_GLIB_REPO_CHECKOUT_OPTIONS = False
        # There is an issue in the way the RepoCheckoutOptions is mapped by glib, as the C
        # struct is using bit fields that are not supported by the introspection.
        # Accessing .disable_fsync and .process_whiteouts thus results in a segfault in
        # libostree.  Re-enable this once it gets fixed.
        if OSTREE_SAFE_GLIB_REPO_CHECKOUT_OPTIONS:
            options = OSTree.RepoCheckoutOptions() # pylint: disable=no-member 
            options.overwrite_mode = OSTree.RepoCheckoutOverwriteMode.UNION_FILES
            options.process_whiteouts = True
            options.disable_fsync = True
            repo.checkout_tree_at(options, rootfs_fd, rootfs, rev)
        else:
            util.check_call(["ostree", "--repo=%s" % self._get_ostree_repo_location(),
                             "checkout",
                             "--union",
                             "--whiteouts",
                             "--fsync=no",
                             rev,
                             rootfs],
                            stdin=DEVNULL,
                            stdout=DEVNULL,
                            stderr=DEVNULL)

    def set_args(self, args):
        self.args = args

        try:
            self.user = args.user
        except (NameError, AttributeError):
            self.user = None
        try:
            self.backend = args.backend
        except (NameError, AttributeError):
            self.backend = None
        if not self.backend:
            self.backend = self.get_atomic_config_item(["default_storage"]) or "ostree"

        try:
            self.setvalues = args.setvalues
        except (NameError, AttributeError):
            pass

    def _pull_image_to_ostree(self, repo, image, upgrade):
        if image.startswith("ostree:"):
            self._check_system_ostree_image(repo, image, upgrade)
        elif self.args.image.startswith("docker:"):
            self._pull_docker_image(repo, image.replace("docker:", ""))
        elif self.args.image.startswith("dockertar:"):
            self._pull_docker_tar(repo, image.replace("dockertar:", ""))
        else: # Assume "oci:"
            self._check_system_oci_image(repo, image, upgrade)

    def pull_image(self):
        if self.backend == "ostree":
            repo = self._get_ostree_repo()
            self._pull_image_to_ostree(repo, self.args.image, True)
        else:
            raise ValueError("Destination not known, please choose --storage=ostree")
        return

    def install_system_container(self, image, name):
        repo = self._get_ostree_repo()
        if not repo:
            raise ValueError("Cannot find a configured OSTree repo")

        self._pull_image_to_ostree(repo, image, False)

        if self.get_system_container_checkout(name):
            util.write_out("%s already present" % (name))
            return

        return self._checkout_system_container(repo, name, image, 0, False)

    def _check_oci_configuration_file(self, conf_path):
        with open(conf_path, 'r') as conf:
            configuration = json.loads(conf.read())
        if not 'root' in configuration or \
           not 'readonly' in configuration['root'] or \
           not configuration['root']['readonly']:
            raise ValueError("Invalid configuration file.  Only readonly images are supported")
        if configuration['root']['path'] != 'rootfs':
            raise ValueError("Invalid configuration file.  Path must be 'rootfs'")

    def _generate_default_oci_configuration(self, destination):
        args = ['/bin/runc', 'spec']
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
        version = str(util.check_output(["/bin/runc", "--version"], stderr=DEVNULL))
        if "version 0" in version:
            runc_commands = ["start", "kill"]
        else:
            runc_commands = ["run", "kill"]
        return ["/bin/runc %s '%s'" % (command, name) for command in runc_commands]

    def _checkout_system_container(self, repo, name, img, deployment, upgrade, values=None, destination=None, extract_only=False):
        if not values:
            values = {}
        imagebranch = SystemContainers._get_ostree_image_branch(img)

        destination = destination or "%s/%s.%d" % (self._get_system_checkout_path(), name, deployment)
        exports = os.path.join(destination, "rootfs/exports")
        unitfile = os.path.join(exports, "service.template")
        unitfileout = os.path.join(SYSTEMD_UNIT_FILES_DEST, "%s.service" % name)

        if not upgrade and os.path.exists(unitfileout):
            raise ValueError("The file %s already exists." % unitfileout)

        util.write_out("Extracting to %s" % destination)

        if hasattr(self.args, 'display') and self.args.display:
            return

        if extract_only:
            rootfs = destination
        else:
            # Under Atomic, get the real deployment location.  It is needed to create the hard links.
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

        os.makedirs(rootfs)

        rev = repo.resolve_rev(imagebranch, False)[1]
        manifest = self._image_manifest(repo, rev)

        rootfs_fd = None
        try:
            rootfs_fd = os.open(rootfs, os.O_DIRECTORY)
            if manifest is None:
                self._checkout_layer(repo, rootfs_fd, rootfs, rev)
            else:
                layers = SystemContainers.get_layers_from_manifest(json.loads(manifest))
                for layer in layers:
                    rev_layer = repo.resolve_rev("%s%s" % (OSTREE_OCIIMAGE_PREFIX, layer.replace("sha256:", "")), False)[1]
                    self._checkout_layer(repo, rootfs_fd, rootfs, rev_layer)
            self._do_syncfs(rootfs, rootfs_fd)
        finally:
            if rootfs_fd:
                os.close(rootfs_fd)

        if extract_only:
            return

        # When installing a new system container, set values in this order:
        #
        # 1) What comes from manifest.json, if present, as default value.
        # 2) What the user sets explictly as --set
        # 3) Values for DESTDIR and NAME
        manifest_file = os.path.join(exports, "manifest.json")
        if os.path.exists(manifest_file):
            with open(manifest_file, "r") as f:
                manifest = json.loads(f.read())
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

        def _write_template(inputfilename, data, values, outfile):
            template = Template(data)
            result = template.safe_substitute(values)
            if '$' in result.replace("$$", ""):
                missing = {x[1] for x in template.pattern.findall(data, template.flags) if len(x[1]) > 0 and x[1] not in values} # pylint: disable=no-member
                raise ValueError("The template file %s still contains unreplaced values for: %s" % \
                                 (inputfilename, ", ".join(missing)))

            outfile.write(result)

        src = os.path.join(exports, "config.json")
        destination_path = os.path.join(destination, "config.json")
        if os.path.exists(src):
            shutil.copyfile(src, destination_path)
        elif os.path.exists(src + ".template"):
            with open(src + ".template", 'r') as infile, open(destination_path, "w") as outfile:
                _write_template(src + ".template", infile.read(), values, outfile)
        else:
            self._generate_default_oci_configuration(destination)

        self._check_oci_configuration_file(destination_path)

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
                    "values" : values}
            info_file.write(json.dumps(info, indent=4))

        if os.path.exists(unitfile):
            with open(unitfile, 'r') as infile:
                systemd_template = infile.read()
        else:
            systemd_template = SYSTEMD_UNIT_FILE_DEFAULT_TEMPLATE

        with open(unitfileout, "w") as outfile:
            _write_template(unitfile, systemd_template, values, outfile)

        sym = "%s/%s" % (self._get_system_checkout_path(), name)
        if os.path.exists(sym):
            os.unlink(sym)
        os.symlink(destination, sym)

        self._systemctl_command("enable", name)
        if upgrade:
            self._systemctl_command("restart", name)
        else:
            self._systemctl_command("start", name)
        return

    def _get_system_checkout_path(self):
        return os.environ.get("ATOMIC_OSTREE_CHECKOUT_PATH") or \
            self.get_atomic_config_item(["checkout_path"]) or \
            "/var/lib/containers/atomic"

    def _get_ostree_repo_location(self):
        if self.user:
            home_dir = os.getenv("HOME")
            return os.path.expanduser("%s/ostree/repo" % home_dir)
        else:
            return os.environ.get("ATOMIC_OSTREE_REPO") or \
                self.get_atomic_config_item(["ostree_repository"]) or \
                "/ostree/repo"

    def _get_ostree_repo(self):
        if not OSTREE_PRESENT:
            return None

        repo_location = self._get_ostree_repo_location()
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

    def update_system_container(self, name):
        self.args.display = False

        repo = self._get_ostree_repo()
        if not repo:
            raise ValueError("Cannot find a configured OSTree repo")

        path = os.path.join(self._get_system_checkout_path(), name)

        next_deployment = 0
        if os.path.realpath(path).endswith(".0"):
            next_deployment = 1
        else:
            next_deployment = 0

        if os.path.exists("%s/%s.%d" % (self._get_system_checkout_path(), name, next_deployment)):
            shutil.rmtree("%s/%s.%d" % (self._get_system_checkout_path(), name, next_deployment))

        with open(os.path.join(self._get_system_checkout_path(), name, "info"), "r") as info_file:
            info = json.loads(info_file.read())

        image = info["image"]
        values = info["values"]

        self._checkout_system_container(repo, name, image, next_deployment, True, values)

    def get_system_containers(self):
        checkouts = self._get_system_checkout_path()
        if not os.path.exists(checkouts):
            return []
        ret = []
        for x in os.listdir(checkouts):
            fullpath = os.path.join(checkouts, x)
            if not os.path.islink(fullpath):
                continue

            with open(os.path.join(fullpath, "info"), "r") as info_file:
                info = json.loads(info_file.read())
                revision = info["revision"] if "revision" in info else ""
                created = info["created"] if "created" in info else ""
                image = info["image"] if "image" in info else ""

            container = {'Image' : image, 'ImageID' : revision, 'Id' : x, 'Created' : created, 'Names' : [x]}
            ret.append(container)
        return ret

    def delete_image(self, image):
        repo = self._get_ostree_repo()
        if not repo:
            return
        imagebranch = SystemContainers._get_ostree_image_branch(image)
        commit_rev = repo.resolve_rev(imagebranch, True)
        if not commit_rev[1]:
            return
        ref = OSTree.parse_refspec(imagebranch)
        repo.set_ref_immediate(ref[1], ref[2], None)

    def inspect_system_image(self, image):
        repo = self._get_ostree_repo()
        if not repo:
            return None
        imagebranch = SystemContainers._get_ostree_image_branch(image)
        return self._inspect_system_branch(repo, imagebranch)

    def _inspect_system_branch(self, repo, imagebranch):
        commit_rev = repo.resolve_rev(imagebranch, False)[1]
        commit = repo.load_commit(commit_rev)[1]

        branch_id = imagebranch.replace("ociimage/", "")
        tag = ":".join(branch_id.rsplit('-', 1))
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

        return {'Id' : image_id, 'RepoTags' : [tag], 'Names' : [], 'Created': timestamp,
                'ImageType' : "System", 'Labels' : labels, 'OSTree-rev' : commit_rev}

    def get_system_images(self, get_all=False, repo=None):
        if repo is None:
            repo = self._get_ostree_repo()
            if repo is None:
                return []
        revs = [x for x in repo.list_refs()[1] if x.startswith(OSTREE_OCIIMAGE_PREFIX) \
                and (get_all or len(x) != len(OSTREE_OCIIMAGE_PREFIX) + 64)]

        return [self._inspect_system_branch(repo, x) for x in revs]

    def _systemctl_command(self, command, name):
        cmd = ["systemctl", command, name]
        util.write_out(" ".join(cmd))
        if not self.args.display:
            util.check_call(cmd)

    def get_system_container_checkout(self, name):
        path = "%s/%s" % (self._get_system_checkout_path(), name)
        if os.path.exists(path):
            return path
        else:
            return None

    def uninstall_system_container(self, name):
        self.args.display = False
        try:
            self._systemctl_command("stop", name)
        except subprocess.CalledProcessError:
            pass
        try:
            self._systemctl_command("disable", name)
        except subprocess.CalledProcessError:
            pass

        if os.path.lexists("%s/%s" % (self._get_system_checkout_path(), name)):
            os.unlink("%s/%s" % (self._get_system_checkout_path(), name))
        for deploy in ["0", "1"]:
            if os.path.exists("%s/%s.%s" % (self._get_system_checkout_path(), name, deploy)):
                shutil.rmtree("%s/%s.%s" % (self._get_system_checkout_path(), name, deploy))
        if os.path.exists(os.path.join(SYSTEMD_UNIT_FILES_DEST, "%s.service" % name)):
            os.unlink(os.path.join(SYSTEMD_UNIT_FILES_DEST, "%s.service" % name))

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
        if tag == "latest":
            name = image.replace("/", "-")
        else:
            name = "%s-%s" % (image.replace("/", "-"), tag)

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
            repo.write_archive_to_mtree(Gio.File.new_for_path(tar), mtree, None, True)
            root = repo.write_mtree(mtree)[1]
            metav = GLib.Variant("a{sv}", {'docker.layer': GLib.Variant('s', layer)})
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
                        _, image, tag = SystemContainers._parse_imagename(m["RepoTags"][0])
                        imagebranch = "%s%s-%s" % (OSTREE_OCIIMAGE_PREFIX, image.replace("sha256:", ""), tag)
                        input_layers = m["Layers"]
                        self._pull_dockertar_layers(repo, imagebranch, temp_dir, input_layers)
                else:
                    repositories = ""
                    repositories_file = os.path.join(temp_dir, "repositories")
                    with open(repositories_file, 'r') as rfile:
                        repositories = rfile.read()
                    _, image, tag = SystemContainers._parse_imagename(list(json.loads(repositories).keys())[0])
                    imagebranch = "%s%s-%s" % (OSTREE_OCIIMAGE_PREFIX, image, tag)
                    input_layers = []
                    for name in os.listdir(temp_dir):
                        if name == "repositories":
                            continue
                        input_layers.append(name + "/layer.tar")
                    self._pull_dockertar_layers(repo, imagebranch, temp_dir, input_layers)
        finally:
            shutil.rmtree(temp_dir)

    def _check_system_ostree_image(self, repo, img, upgrade):
        imagebranch = img.replace("ostree:", "")
        current_rev = repo.resolve_rev(imagebranch, True)
        if not upgrade and current_rev[1]:
            return False
        remote, branch = imagebranch.split(":")
        return repo.pull(remote, [branch], 0, None)

    def _check_system_oci_image(self, repo, img, upgrade):
        _, image, tag = SystemContainers._parse_imagename(img.replace("oci:", ""))
        imagebranch = "%s%s-%s" % (OSTREE_OCIIMAGE_PREFIX, image.replace("sha256:", ""), tag)
        current_rev = repo.resolve_rev(imagebranch, True)
        if not upgrade and current_rev[1]:
            return False

        manifest = self._skopeo_get_manifest(img)
        layers = SystemContainers.get_layers_from_manifest(manifest)
        missing_layers = []
        for i in layers:
            layer = i.replace("sha256:", "")
            if not repo.resolve_rev("%s%s" % (OSTREE_OCIIMAGE_PREFIX, layer), True)[1]:
                missing_layers.append(layer)
                util.write_out("Missing layer %s" % layer)

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
                            if layer in missing_layers:
                                layers_to_import[layer] = layer_file

            SystemContainers._import_layers_into_ostree(repo, imagebranch, manifest, layers_to_import)
        finally:
            if layers_dir:
                shutil.rmtree(layers_dir)
        return True

    @staticmethod
    def _get_commit_metadata(repo, rev, key):
        commit = repo.load_commit(rev)[1]
        metadata = commit.get_child_value(0)
        if key not in metadata.keys():
            return None
        return metadata[key]

    def extract_system_container(self, img, destination):
        repo = self._get_ostree_repo()
        if not repo:
            return False
        return self._checkout_system_container(repo, img, img, 0, False, destination=destination, extract_only=True)

    @staticmethod
    def _get_ostree_image_branch(img):
        if "ostree:" in img:
            imagebranch = img.replace("ostree:", "")
        else: # assume "oci:" image
            _, image, tag = SystemContainers._parse_imagename(img.replace("oci:", "").replace("docker:", ""))
            imagebranch = "%s%s-%s" % (OSTREE_OCIIMAGE_PREFIX, image.replace("sha256:", ""), tag)
        return imagebranch

    def has_system_container_image(self, img):
        repo = self._get_ostree_repo()
        if not repo:
            return False
        try:
            imagebranch = SystemContainers._get_ostree_image_branch(img)
            return repo.resolve_rev(imagebranch, False)[0]
        except: #pylint: disable=bare-except
            return False

    def _pull_dockertar_layers(self, repo, imagebranch, temp_dir, input_layers):
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

        manifest = json.dumps({"Layers" : layers_ordered})

        layers_to_import = {}
        for k, v in layers.items():
            layers_to_import[layers_map[k]] = v
        SystemContainers._import_layers_into_ostree(repo, imagebranch, manifest, layers_to_import)
