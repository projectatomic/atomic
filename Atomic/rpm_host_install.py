import re
import os
from . import util
from . import rpmwriter
import tempfile
import shutil
import hashlib
import selinux

RPM_NAME_PREFIX = "atomic-container"

class RPMHostInstall(object):

    @staticmethod
    def _copyfile(selinux_hnd, src, dest, try_hardlink=False):

        if selinux_hnd is not None:
            mode = 0o755
            try:
                mode = os.stat(src).st_mode
            except OSError:
                pass

            ctx = selinux.selabel_lookup_raw(selinux_hnd, str(dest), mode)
            selinux.setfscreatecon_raw(ctx[1])

        if os.path.isdir(src):
            # add the directory only if it is empty, so we don't delete directories that
            # weren't added by us.  Anyway a non empty directory would be created by
            # its children.
            if len(os.listdir(src)) == 0:
                os.mkdir(dest)
                return True
        elif os.path.islink(src):
            linkto = os.readlink(src)
            os.symlink(linkto, dest)
            return True
        else:
            file_copied = False
            # newer version of Skopeo/SELinux use the same SELinux context for system containers
            # files as the host files at the same location i.e. /exports/hostfs/foo -> /foo.
            if try_hardlink and selinux_hnd is not None:
                src_label = selinux.getfilecon(src)
                # Files have the same label, we can use a hard link.
                if src_label[1] == ctx[1]:
                    try:
                        os.link(src, dest)
                        file_copied = True
                    except:  # pylint: disable=bare-except
                        pass

            # fallback to file copy.
            if not file_copied:
                # we cannot use shutil.copy2() or shutil.copystat() here as it would override the
                # security.selinux xattr.
                shutil.copy(src, dest)
                shutil.copymode(src, dest)
            return True
        return False

    @staticmethod
    def _do_rename_path(path, rename_files):
        path_split = path.split('/')
        path = ""
        for i in path_split[1:]:
            path = "{}/{}".format(path, i)
            path = rename_files.get(path, path)
        return path

    @staticmethod
    def file_checksum(path, blocksize=(1<<20)):
        if not os.path.exists(path) or os.path.isdir(path):
            return "0"

        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(blocksize)
                if chunk == None or len(chunk) == 0:
                    break
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _should_use_hard_link(dest_path):
        return dest_path.startswith("/usr/")

    @staticmethod
    def rm_add_files_to_host(old_installed_files_checksum, exports, prefix="/", files_template=None, values=None, rename_files=None, use_links=True):
        # if any file was installed on the host delete it
        if old_installed_files_checksum:
            for path, checksum in old_installed_files_checksum.items():
                new_checksum = RPMHostInstall.file_checksum(path)
                if new_checksum != checksum:
                    # Do not delete the file if it was modified.
                    util.write_out("Will not delete %s as it was manually modified." % path, lf="\n")
                    continue
                try:
                    os.remove(path)
                except OSError:
                    pass

        if not exports:
            return []

        templates_set = set(files_template or [])

        # if there is a directory hostfs/ under exports, copy these files to the host file system.
        hostfs = os.path.join(exports, "hostfs")
        new_installed_files_checksum = {}
        if not os.path.exists(hostfs):
            return new_installed_files_checksum

        selinux_hnd = None
        try:
            if os.getuid() == 0 and selinux.is_selinux_enabled() != 0:
                selinux_hnd = selinux.selabel_open(selinux.SELABEL_CTX_FILE, None, 0)

            for root, dirs, files in os.walk(hostfs):
                rel_root_path = os.path.relpath(root, hostfs)
                if not os.path.exists(os.path.join(prefix, rel_root_path)):
                    os.makedirs(os.path.join(prefix, rel_root_path))
                for f in dirs + files:
                    src_file = os.path.join(root, f)
                    dest_path = os.path.join(prefix, rel_root_path, f)
                    rel_dest_path = os.path.join("/", rel_root_path, f)

                    # If rename_files is set, rename the destination file
                    if rename_files:
                        rel_dest_path = RPMHostInstall._do_rename_path(rel_dest_path, rename_files)
                        dest_path = os.path.join(prefix or "/", os.path.relpath(rel_dest_path, "/"))

                    if os.path.exists(dest_path):
                        if os.path.isfile(dest_path):
                            util.write_out("File %s already exists" % os.path.normpath(dest_path), lf="\n")
                        continue

                    if not os.path.exists(os.path.dirname(dest_path)):
                        os.makedirs(os.path.dirname(dest_path))

                    created = False
                    if rel_dest_path in templates_set:
                        with open(src_file, 'r') as src_file_obj:
                            data = src_file_obj.read()

                        if selinux_hnd is not None:
                            ctx = selinux.selabel_lookup_raw(selinux_hnd, str(dest_path), os.stat(src_file).st_mode)
                            selinux.setfscreatecon_raw(ctx[1])

                        util.write_template(src_file, data, values or {}, dest_path)
                        shutil.copymode(src_file, dest_path)
                        created = True
                    else:
                        try_hardlink = use_links and RPMHostInstall._should_use_hard_link(dest_path)
                        created = RPMHostInstall._copyfile(selinux_hnd, src_file, dest_path, try_hardlink=try_hardlink)

                    if created:
                        new_installed_files_checksum[rel_dest_path] = RPMHostInstall.file_checksum(dest_path)
        finally:
            if selinux_hnd is not None:
                selinux.setfscreatecon_raw(None)

        return new_installed_files_checksum


    @staticmethod
    def generate_rpm_from_rootfs(rootfs, temp_dir, name, image_id, labels, include_containers_file, display=False, installed_files=None, defaultversion='1'):
        rpm_content = os.path.join(temp_dir, "rpmroot")

        included_rpm = os.path.join(rootfs, "rootfs", "exports", "container.rpm")
        if os.path.exists(included_rpm):
            return included_rpm

        summary = labels.get('atomic.summary', name)
        version = labels.get("atomic.version", defaultversion)
        release = labels.get("atomic.release", image_id)
        license_ = labels.get("atomic.license", "GPLv2")
        url = labels.get("atomic.url")
        requires = labels.get("atomic.requires")
        provides = labels.get("atomic.provides")
        conflicts = labels.get("atomic.conflicts")
        description = labels.get("atomic.description")

        result_dir = os.path.join(temp_dir, "build")
        if not os.path.exists(result_dir):
            os.makedirs(result_dir)

        rpm_name = "atomic-container-%s" % name
        rpm_out = os.path.join(result_dir, "%s.rpm" % rpm_name)
        def split_name_version(pkg):
            r = r"([a-zA-Z0-9_\-\.\+]+)(.*)"
            s = re.search(r, pkg)
            return s.group(1), s.group(2)

        files_to_install = installed_files or []
        if include_containers_file:
            files_to_install.append("/usr/lib/systemd/system/%s.service" % name)
            for root, dirs, files in os.walk(os.path.join(rpm_content, "usr/lib/containers/atomic", name)):
                rel_path = os.path.relpath(root, rpm_content)
                for f in dirs + files:
                    p = os.path.join("/", rel_path, f)
                    files_to_install.append(p)

        with open(rpm_out, "wb") as f, open('/dev/null', 'wb') as devnull:
            writer = rpmwriter.RpmWriter(f, rpm_content, rpm_name, version, release, summary, description or "", license_=license_ or "", url=url or "", stderr=devnull, whitelist=files_to_install)
            if requires is not None:
                for name, version in [split_name_version(i) for i in requires.split(',')]:
                    writer.add_require(name, version)
            if conflicts is not None:
                for name, version in [split_name_version(i) for i in conflicts.split(',')]:
                    writer.add_conflict(name, version)
            if provides is not None:
                for name in provides.split(','):
                    writer.add_provide(name)

            if not display:
                writer.generate()

        return temp_dir

    @staticmethod
    def find_rpm(tmp_dir):
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

    @staticmethod
    def generate_rpm(name, image_id, labels, exports, destination, values=None, installed_files=None, installed_files_template=None, rename_files=None, defaultversion='1'):

        if values == None:
            values = {}

        # If rpm.spec or rpm.spec.template exist, copy them to the checkout directory, processing the .template version.
        if os.path.exists(os.path.join(exports, "rpm.spec.template")):
            with open(os.path.join(exports, "rpm.spec.template"), "r") as f:
                spec_content = f.read()
            util.write_template("rpm.spec.template", spec_content, values, os.path.join(destination, "rpm.spec"))
        elif os.path.exists(os.path.join(exports, "rpm.spec")):
            shutil.copyfile(os.path.join(exports, "rpm.spec"), os.path.join(destination, "rpm.spec"))

        temp_dir = tempfile.mkdtemp()
        orig_name = dest_path = None
        try:
            rpm_content = os.path.join(temp_dir, "rpmroot")
            rootfs = os.path.join(rpm_content, "usr/lib/containers/atomic", name)
            os.makedirs(rootfs)
            if installed_files is None:
                checksums = RPMHostInstall.rm_add_files_to_host(None, exports, rpm_content, files_template=installed_files_template, values=values, rename_files=rename_files)
                installed_files = checksums.keys()
            rpm_root = RPMHostInstall.generate_rpm_from_rootfs(destination, temp_dir, name, image_id, labels, include_containers_file=False, installed_files=installed_files, defaultversion=defaultversion)
            rpm_file = RPMHostInstall.find_rpm(rpm_root)
            if rpm_file:
                orig_name = "atomic-container-{}.rpm".format(name)
                dest_path = os.path.join(destination, orig_name)
                if os.path.exists(dest_path):
                    os.unlink(dest_path)
                shutil.move(rpm_file, dest_path)
        finally:
            shutil.rmtree(temp_dir)
        return orig_name, dest_path, installed_files

    @staticmethod
    def install_rpm(rpm):
        """
        :param rpm_file: str, name of the rpm to install, is passed to dnf/yum
        :return: None
        """
        if os.path.exists("/run/ostree-booted"):
            raise ValueError("This doesn't work on Atomic Host yet")
        elif os.path.exists("/usr/bin/dnf"):
            util.check_call(["dnf", "install", "-C", "-y", rpm])
        else:
            util.check_call(["yum", "install", "-C", "-y", rpm])

    @staticmethod
    def uninstall_rpm(rpm):
        """
        :param rpm: str, name of the rpm to uninstall, is passed to dnf/yum
        :return: None
        """
        if os.path.exists("/run/ostree-booted"):
            raise ValueError("This doesn't work on Atomic Host yet")
        elif os.path.exists("/usr/bin/dnf"):
            util.check_call(["dnf", "remove", "-y", rpm])
        else:
            util.check_call(["yum", "remove", "-y", rpm])
