import os
from . import util
import tempfile
import shutil

RPM_NAME_PREFIX = "atomic-container"

class RPMHostInstall(object):

    @staticmethod
    def _do_rename_path(path, rename_files):
        path_split = path.split('/')
        path = ""
        for i in path_split[1:]:
            path = "{}/{}".format(path, i)
            path = rename_files.get(path, path)
        return path

    @staticmethod
    def rm_add_files_to_host(old_installed_files, exports, prefix="/", files_template=None, values=None, rename_files=None):
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
                    if rename_files:
                        rel_dest_path = RPMHostInstall._do_rename_path(rel_dest_path, rename_files)
                        dest_path = os.path.join(prefix or "/", os.path.relpath(rel_dest_path, "/"))

                    if os.path.exists(dest_path):
                        util.write_out("File %s already exists." % dest_path, lf="\n")
                        continue

                    if rel_dest_path in templates_set:
                        with open(src_file, 'r') as src_file_obj:
                            data = src_file_obj.read()
                        util.write_template(src_file, data, values or {}, dest_path)
                        shutil.copystat(src_file, dest_path)
                    else:
                        shutil.copy2(src_file, dest_path)

                    new_installed_files.append(rel_dest_path)
            new_installed_files.sort()  # just for an aesthetic reason in the info file output

        return new_installed_files

    @staticmethod
    def _generate_spec_file(destdir, name, summary, license_, image_id, version="1.0", release="1", url=None,
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
                spec += "%%config \"%s\"\n" % os.path.join("/", rel_path, f)

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

    @staticmethod
    def generate_rpm_from_rootfs(rootfs, temp_dir, name, image_id, labels, include_containers_file, display=False, installed_files=None, defaultversion='1'):
        rpm_content = os.path.join(temp_dir, "rpmroot")
        spec_file = os.path.join(temp_dir, "container.spec")

        included_rpm = os.path.join(rootfs, "rootfs", "exports", "container.rpm")
        if os.path.exists(included_rpm):
            return included_rpm

        summary = labels.get('summary', name)
        version = labels.get("version", defaultversion)
        release = labels.get("release", image_id)
        license_ = labels.get("license", "GPLv2")
        url = labels.get("url")
        source0 = labels.get("source0")
        requires = labels.get("requires")
        provides = labels.get("provides")
        conflicts = labels.get("conflicts")
        description = labels.get("description")

        if os.path.exists(os.path.join(rootfs, "rpm.spec")):
            with open(os.path.join(rootfs, "rpm.spec"), "r") as f:
                spec_content = f.read()
        else:
            spec_content = RPMHostInstall._generate_spec_file(rpm_content, name, summary, license_, image_id, version=version,
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
        if not display:
            util.check_call(cmd)
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
                installed_files = RPMHostInstall.rm_add_files_to_host(None, exports, rpm_content, files_template=installed_files_template, values=values, rename_files=rename_files)
            rpm_root = RPMHostInstall.generate_rpm_from_rootfs(destination, temp_dir, name, image_id, labels, include_containers_file=False, installed_files=installed_files, defaultversion=defaultversion)
            rpm_file = RPMHostInstall.find_rpm(rpm_root)
            if rpm_file:
                dest_path = os.path.join(destination, "container.rpm")
                if os.path.exists(dest_path):
                    os.unlink(dest_path)
                orig_name = os.path.basename(rpm_file)
                shutil.move(rpm_file, dest_path)
        finally:
            shutil.rmtree(temp_dir)
        return (orig_name, dest_path)
