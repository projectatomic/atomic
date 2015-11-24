import os
import sys
import rpm
import Atomic.util as util
from filecmp import dircmp
import Atomic.mount as mount


class DiffHelpers(object):
    """
    Helper class for the diff function
    """
    def __init__(self, args):
        self.args = args
        self.json_out = {}

    def build_rpm_list(self, image_list):
        """
        Build and return a list of rpms
        :param image_list:
        :return: list
        """
        rpm_image_list = []
        for image in image_list:
            rpm_image_list.append(RpmDiff(image.chroot, image.name, self.args.names_only))
        self.are_all_images_rpm(rpm_image_list)
        return rpm_image_list

    @staticmethod
    def are_all_images_rpm(image_list):
        """
        Stub function to determine if all images are RPM based after mounting
        :param image_list:
        :return: bool True or False
        """
        for image in image_list:
            if not image.is_rpm:
                raise ValueError("{0} is not RPM based.".format(image.name))

    @staticmethod
    def _cleanup(image_list):
        """
        Class the cleanup def
        :param image_list:
        :return: None
        """
        for image in image_list:
            image._remove()

    @staticmethod
    def create_image_list(images):
        """
        Instantiate each image into a class and then into
        image_list
        :param images:
        :return: list of image class instantiations
        """
        image_list = []
        for image in images:
            image_list.append(DiffObj(image))
        return image_list

    def output_files(self, images, image_list):
        """
        Prints out the file differences when applicable
        :param images:
        :param image_list:
        :return: None
        """
        file_diff = DiffFS(image_list[0].chroot, image_list[1].chroot)
        for image in image_list:
            self.json_out[image.name] = {'{}_only'.format(image.name): file_diff._get_only(image.chroot)}
        self.json_out['files_differ'] = file_diff.common_diff

        if not self.args.json:
            file_diff.print_results(images[0], images[1])
            util.writeOut("\n")

    def output_rpms(self, rpm_image_list):
        """
        Prints out the differences in RPMs when applicable
        :param rpm_image_list:
        :return: None
        """
        ip = RpmPrint(rpm_image_list)
        if not self.args.json:
            if ip.has_diff:
                ip._print_diff(self.args.verbose)
            else:
                util.writeOut("\n{} and {} have no different RPMs".format(ip.i1.name, ip.i2.name))

        # Output JSON content
        else:
            rpm_json = ip._rpm_json()
            for image in rpm_json.keys():
                if image not in self.json_out:
                    self.json_out[image] = rpm_json[image]
                else:
                    _tmp = self.json_out[image]
                    _tmp.update(rpm_json[image])
                    self.json_out[image] = _tmp


class DiffObj(object):
    def __init__(self, docker_name):
        self.dm = mount.DockerMount("/tmp", mnt_mkdir=True)
        self.name = docker_name
        self.root_path = self.dm.mount(self.name)
        self.chroot = os.path.join(self.root_path, "rootfs")

    def _remove(self):
        """
        Stub to unmount, remove the devmapper device (if needed), and
        remove any temporary containers used
        :return: None
        """
        self.dm.unmount()


class RpmDiff(object):
    """
    Class for handing the parsing of images during an
    atomic diff
    """
    def __init__(self, chroot, name, names_only):
        self.chroot = chroot
        self.name = name
        self.is_rpm = self._is_rpm_based()
        self.rpms = None
        self.release = None
        self.names_only = names_only
        if self.is_rpm:
            self._get_rpm_content()

    def _get_rpm_content(self):
        """
        Populates the release and RPM information
        :return: None
        """
        self.rpms = self._get_rpms(self.chroot)
        self.release = self._populate_rpm_content(self.chroot)

    def _is_rpm_based(self):
        """
        Determines if the image is based on RPM
        :return: bool True or False
        """
        if os.path.exists(os.path.join(self.chroot, 'usr/bin/rpm')):
            return True
        else:
            return False

    def _get_rpms(self, chroot_os):
        """
        Pulls the NVRs of the RPMs in the image
        :param chroot_os:
        :return: sorted list pf RPM NVRs
        """
        ts = rpm.TransactionSet(chroot_os)
        ts.setVSFlags((rpm._RPMVSF_NOSIGNATURES | rpm._RPMVSF_NODIGESTS))
        image_rpms = []
        for hdr in ts.dbMatch():  # No sorting  # pylint: disable=no-member
            if hdr['name'] == 'gpg-pubkey':
                continue
            else:
                if not self.names_only:
                    foo = "{0}-{1}-{2}".format(hdr['name'],
                                               hdr['epochnum'],
                                               hdr['version'])
                else:
                    foo = "{0}".format(hdr['name'])
                image_rpms.append(foo)
        return sorted(image_rpms)

    @staticmethod
    def _populate_rpm_content(chroot_os):
        """
        Get the release on the imageTrue
        :param chroot_os:
        :return: string release name
        """
        etc_release_path = os.path.join(chroot_os,
                                        "etc/redhat-release")
        os_release = open(etc_release_path).read()
        return os_release


class RpmPrint(object):
    """
    Class to handle the output of atomic diff
    """
    def __init__(self, image_list):
        def _max_rpm_name_length(all_rpms):
            _max = max([len(x) for x in all_rpms])
            return _max if _max >= 30 else 30

        self.image_list = image_list
        self.i1, self.i2 = self.image_list
        self.all_rpms = sorted(list(set(self.i1.rpms) | set(self.i2.rpms)))
        self._max = _max_rpm_name_length(self.all_rpms)
        self.two_col = "{0:" + str(self._max) + "} | {1:" \
                       + str(self._max) + "}"
        self.has_diff = False if set(self.i1.rpms) == set(self.i2.rpms) \
            else True

    def _print_diff(self, be_verbose):
        """
        Outputs the diff information in columns
        :return: None
        """
        util.writeOut("")
        util.writeOut(self.two_col.format(self.i1.name, self.i2.name))
        util.writeOut(self.two_col.format("-"*self._max, "-"*self._max))
        self._print_release()
        util.writeOut(self.two_col.format("-"*self._max, "-"*self._max))
        for rpm in self.all_rpms:
            if (rpm in self.i1.rpms) and (rpm in self.i2.rpms):
                if be_verbose:
                    util.writeOut(self.two_col.format(rpm, rpm))
            elif (rpm in self.i1.rpms) and not (rpm in self.i2.rpms):
                util.writeOut(self.two_col.format(rpm, ""))
            elif not (rpm in self.i1.rpms) and (rpm in self.i2.rpms):
                util.writeOut(self.two_col.format("", rpm))

    def _print_release(self):
        """
        Prints the release information and splits based on the column length
        :return: None
        """
        step = self._max - 2
        r1_split = [self.i1.release.strip()[i:i+step] for i in range(0, len(self.i1.release.rstrip()), step)]
        r2_split = [self.i2.release.strip()[i:i+step] for i in range(0, len(self.i2.release.rstrip()), step)]
        for n in list(range(max(len(r1_split), len(r2_split)))):
            col1 = r1_split[n] if 0 <= n < len(r1_split) else ""
            col2 = r2_split[n] if 0 <= n < len(r2_split) else ""
            util.writeOut(self.two_col.format(col1, col2))

    def _rpm_json(self):
        """
        Pretty prints the output in json format
        :return: None
        """
        def _form_image_json(image, exclusive, common):
            return {
                "release": image.release,
                "all_rpms": image.rpms,
                "exclusive_rpms": exclusive,
                "common_rpms": common
            }
        l1_diff = sorted(list(set(self.i1.rpms) - set(self.i2.rpms)))
        l2_diff = sorted(list(set(self.i2.rpms) - set(self.i1.rpms)))
        common = sorted(list(set(self.i1.rpms).intersection(self.i2.rpms)))
        json_out = {}
        json_out[self.i1.name] = _form_image_json(self.i1, l1_diff, common)
        json_out[self.i2.name] = _form_image_json(self.i2, l2_diff, common)
        return json_out


class DiffFS(object):
    """
    Primary class for doing a diff on two docker objects
    """
    def __init__(self, chroot_left, chroot_right):
        self.compare = dircmp(chroot_left, chroot_right)
        self.left = []
        self.right = []
        self.common_diff = []
        self.chroot_left = chroot_left
        self.chroot_right = chroot_right
        self.delta(self.compare)

    def _get_only(self, _chroot):
        """
        Simple function to return the right diff using the chroot path
        as a key
        :param _chroot:
        :return: list of diffs for the chroot path
        """
        return self.left if _chroot == self.chroot_left else self.right

    @staticmethod
    def _walk(walkdir):
        """
        Walks the filesystem at the given walkdir
        :param walkdir:
        :return: list of files found
        """
        file_list = []
        walk = os.walk(walkdir)
        for x in walk:
            (_dir, dir_names, files) = x
            if len(dir_names) < 1 and len(files) > 0:
                for _file in files:
                    file_list.append(os.path.join(_dir, _file))
            elif len(dir_names) < 1 and len(files) < 1:
                file_list.append(_dir)
        return file_list

    def delta(self, compare_obj):
        """
        Primary function for performing the recursive diff
        :param compare_obj:  a dircomp object
        :return: None
        """
        # Removing the fs path /tmp/<docker_obj>/rootfs
        _left_path = compare_obj.left.replace(self.chroot_left, '')
        _right_path = compare_obj.right.replace(self.chroot_right, '')

        # Add list of common files but files appear different
        for common in compare_obj.diff_files:
            self.common_diff.append(os.path.join(_left_path, common))

        # Add the diffs from left
        for left in compare_obj.left_only:
            fq_left = os.path.join(_left_path, left)
            self.left.append(fq_left)
            if os.path.isdir(fq_left):
                walk = self._walk(fq_left)
                self.left += walk

        # Add the diffs from right
        for right in compare_obj.right_only:
            fq_right = os.path.join(_right_path, right)
            self.right.append(os.path.join(_right_path, right))
            if os.path.isdir(fq_right):
                walk = self._walk(fq_right)
                self.right += walk

        # Follow all common subdirs
        for _dir in compare_obj.subdirs.values():
            self.delta(_dir)

    def print_results(self, left_docker_obj, right_docker_obj):
        """
        Pretty output for the results of the filesystem diff
        :param left_docker_obj:
        :param right_docker_obj:
        :return:
        """
        def _print_diff(file_list):
            for _file in file_list:
                util.writeOut("{0}{1}".format(5*" ", _file))

        if all([len(self.left) == 0, len(self.right) == 0,
                len(self.common_diff) == 0]):
            util.writeOut("\nThere are no file differences between {0} "
                          "and {1}".format(left_docker_obj, right_docker_obj))
        if len(self.left) > 0:
            util.writeOut("\nFiles only in {}:".format(left_docker_obj))
            _print_diff(self.left)
        if len(self.right) > 0:
            util.writeOut("\nFiles only in {}:".format(right_docker_obj))
            _print_diff(self.right)
        if len(self.common_diff):
            util.writeOut("\nCommon files that are different:")
            _print_diff(self.common_diff)
