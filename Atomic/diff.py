import os
import sys
import rpm
import tempfile
from . import util
from . import mount
from . import Atomic
from Atomic.client import get_docker_client
from docker.errors import NotFound
import json


CHOICES=['link', 'nlink', 'mode', 'type', 'time', 'uid', 'gid', 'size', 'sha256digest']

def cli(subparser):
    # atomic diff
    diffp = subparser.add_parser(
    "diff", help=_("Show differences between two container images, file diff or RPMS."),
    epilog="atomic diff 'image1|container1' 'image2|container2'")
    diffp.set_defaults(_class=Diff, func='diff_tty')
    diffp.add_argument("compares", nargs=2,
                       help=_("Container images to compare"))
    diffp.add_argument("-m", "--metadata", default=False, action='store_true', dest='metadata',
                       help=_("Compare images' metadata"))
    diffp.add_argument("-k", "--keywords", nargs='?',
                       action='append',
                       choices=['all'] + CHOICES,
                       help=_("Exclusive keywords to be used for file level comparision"))
    diffp.add_argument("-n", "--no-files", default=False, action='store_true',
                       help=_("Do not perform a file diff between the docker objects"))
    diffp.add_argument("--names-only", default=False,
                       action='store_true', help=_("Only compare RPM names and not versions"))
    diffp.add_argument("-r", "--rpms", default=False, action='store_true',
                       help=_("List different rpms between the container images."))
    disp_group = diffp.add_mutually_exclusive_group()
    disp_group.add_argument("--json", default=False, action='store_true',
                            help=_("output json"))
    disp_group.add_argument("-v", "--verbose", default=False, action='store_true',
                            help=_("Show verbose output, listing all RPMs"))



class Diff(Atomic):

    def diff_tty(self):
        if self.args.no_files and not self.args.metadata and not self.args.rpms:
            raise ValueError("When repressing a file diff, you must choose to diff RPMs (-r) or metadata (-m)")

        diff_dict = self.diff()
        if self.args.json:
            util.output_json(diff_dict)

    def diff(self):
        '''
        Allows you to 'diff' the RPMs between two different docker images|containers.
        :return: None
        '''
        if self.args.debug:
            util.write_out(str(self.args))

        helpers = DiffHelpers(self.args)
        images = self.args.compares
        # Check to make sure each input is valid
        for image in images:
            self.get_input_id(image)

        image_list = helpers.create_image_list(images, self.args)
        try:
            # Set up RPM classes and make sure each docker object
            # is RPM-based
            rpm_image_list = []
            if self.args.rpms:
                for image in image_list:
                    rpmimage = RpmDiff(image.chroot, image.name, self.args.names_only)
                    if not rpmimage.is_rpm:
                        helpers.cleanup(image_list)
                        raise ValueError("{0} is not RPM based.".format(rpmimage.name))
                    rpmimage.get_rpm_content()
                    rpm_image_list.append(rpmimage)

            if not self.args.no_files:
                helpers.output_files(images, image_list)

            if self.args.rpms:
                helpers.output_rpms(rpm_image_list)

            if self.args.metadata:
                compare_meta = CompareMetaData(image_list)
                compare_meta.compare()
                helpers.output_metadata(image_list)

            # Clean up
            helpers.cleanup(image_list)

            return helpers.json_out

        except KeyboardInterrupt:
            util.write_out("Quitting...")
            helpers.cleanup(image_list)
        return []

class DiffHelpers(object):
    """
    Helper class for the diff function
    """
    def __init__(self, args):
        self.args = args
        self.json_out = {}

    @staticmethod
    def cleanup(image_list):
        """
        Class the cleanup def
        :param image_list:
        :return: None
        """
        for image in image_list:
            image.remove()

    @staticmethod
    def create_image_list(images, args):
        """
        Instantiate each image into a class and then into
        image_list
        :param images:
        :return: list of image class instantiations
        """
        image_list = []
        for image in images:
            try:
                image_list.append(DiffObj(image, args))
            except mount.SelectionMatchError as e:
                if len(image_list) > 0:
                    DiffHelpers.cleanup(image_list)
                util.write_err("{}".format(e))
                sys.exit(1)
        return image_list

    def output_files(self, images, image_list):
        img_left, img_right = (x for x in image_list)
        foo = img_left.manifest_file_name
        img_right.manifest_file_name = foo
        results = img_right.validation_result

        file_diff = DiffFS(image_list)
        for image in image_list:
            self.json_out[image.name] = {'unique_files': file_diff.get_only(image.chroot)}

        self.json_out['files_differ'] = file_diff.common_diff

        if not self.args.json:
            file_diff.print_results(images[0], images[1])
            util.write_out("\n")
        # It might make sense to save the mtree results
        # for the user with a switch
        return results

    def output_rpms(self, rpm_image_list):
        """
        Prints out the differences in RPMs when applicable
        :param rpm_image_list:
        :return: None
        """
        ip = RpmPrint(rpm_image_list)
        if not self.args.json:
            if ip.has_diff:
                ip.print_diff(self.args.verbose)
            else:
                if self.args.names_only:
                    util.write_out("\n{} and {} has the same RPMs.  Versions may differ.  Remove --names-only"
                                   " to see if there are version differences.".format(ip.i1.name, ip.i2.name))
                else:
                    util.write_out("\n{} and {} have no different RPMs".format(ip.i1.name, ip.i2.name))

        # Output JSON content
        else:
            rpm_json = ip.rpm_json()
            for image in rpm_json.keys():
                if image not in self.json_out:
                    self.json_out[image] = rpm_json[image]
                else:
                    _tmp = self.json_out[image]
                    _tmp.update(rpm_json[image])
                    self.json_out[image] = _tmp

    def output_metadata(self, image_list):
        if not self.args.json:
            for image in image_list:
                if image.name not in self.json_out:
                    self.json_out[image.name] = {}
                self.json_out[image.name]['unique_metadata'] = image.metadata_results
        else:
            img_obj1, img_obj2 = (x for x in image_list)
            if all([not img_obj1.metadata_results, not img_obj2.metadata_results]):
                util.write_out("\n{} and {} have no differences in their metadata".format(img_obj1.name, img_obj2.name))
            for image in image_list:
                util.write_out("\nMetadata only in {}:".format(image.name))
                util.output_json(image.metadata_results)


class DiffObj(object):
    def __init__(self, docker_name, args):
        self.args = args
        self.dm = mount.DockerMount(tempfile.mkdtemp(), mnt_mkdir=True)
        self.name = docker_name
        self.root_path = self.dm.mount(self.name)
        chroot = os.path.join(self.root_path, "rootfs")
        if os.path.exists(chroot):
            self.chroot = chroot
        else:
            self.chroot = self.root_path
        self.metadata_results = None
        self._manifest_file_name = None
        self._validation_results= None
        if self.args.keywords is None:
            self.keywords = CHOICES
        elif 'all' in self.args.keywords:
            self.keywords = CHOICES
        else:
            self.keywords = self.args.keywords

    def remove(self):
        """
        Stub to unmount, remove the devmapper device (if needed), and
        remove any temporary containers used
        :return: None
        """
        self.dm.unmount()

    @property
    def inspect_data(self):
        d = get_docker_client()
        try:
            return d.inspect_image(self.name)
        except NotFound:
            try:
                return d.inspect_container(self.name)
            except NotFound:
                raise ValueError("Unable to find container or image named '{}'".format(self.name))

    def generate_mtree(self):
        rc, mtree_output, stderr = util.generate_validation_manifest(img_rootfs=self.chroot,
                                                                     keywords=" ".join(self.keywords))
        if rc != 0:
            raise ValueError("Unable to generate manifest for {}. \nReason: {}\n".format(self.name, stderr))
        mtree_file= tempfile.NamedTemporaryFile(mode="wb", delete=False)
        if self.args.debug:
            util.write_out("Saving mtree manifest as {}".format(mtree_file.name))
        mtree_file.write(mtree_output)
        mtree_file.close()
        self._manifest_file_name = mtree_file.name

    @property
    def manifest_file_name(self):
        if not self._manifest_file_name:
            self.generate_mtree()
        return self._manifest_file_name

    @manifest_file_name.setter
    def manifest_file_name(self, value):
        self._manifest_file_name = value

    @property
    def validation_result(self):
        if not self._validation_results:
            self.validate()
        return self._validation_results

    def validate(self):
        rc, results, stderr = util.validate_manifest(self._manifest_file_name, img_rootfs=self.chroot,
                                                     keywords=" ".join(self.keywords), json_out=True)
        if rc not in [0, 1]:
            raise ValueError("Unable to validate manifest against {}. \nReason: {}\n".format(self.name, stderr))
        self._validation_results = json.loads(results.decode('utf-8'))

        if self.args.debug:
            # if in debug, save the manifest validation results too
            mtree_validate = tempfile.NamedTemporaryFile(mode="w", delete=False)
            mtree_validate.write(json.dumps(self._validation_results))
            mtree_validate.close()
            util.write_out("Saving validation manifest as {}".format(mtree_validate.name))
        else:
            # Remove the manifest file
            os.remove(self._manifest_file_name)



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

    def get_rpm_content(self):
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
        ts.setVSFlags((rpm._RPMVSF_NOSIGNATURES | rpm._RPMVSF_NODIGESTS)) # pylint: disable=protected-access
        image_rpms = []
        enc=sys.getdefaultencoding()
        for hdr in ts.dbMatch():  # No sorting  # pylint: disable=no-member
            name = hdr['name'].decode(enc)
            if name == 'gpg-pubkey':
                continue
            else:
                if not self.names_only:
                    foo = "{0}-{1}-{2}-{3}".format(name,
                                                   hdr['epochnum'],
                                                   hdr['version'].decode(enc),
                                                   hdr['release'])

                else:
                    foo = "{0}".format(name)
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

    def print_diff(self, be_verbose):
        """
        Outputs the diff information in columns
        :return: None
        """
        util.write_out("")
        util.write_out(self.two_col.format(self.i1.name, self.i2.name))
        util.write_out(self.two_col.format("-"*self._max, "-"*self._max))
        self._print_release()
        util.write_out(self.two_col.format("-"*self._max, "-"*self._max))
        for r in self.all_rpms:
            if (r in self.i1.rpms) and (r in self.i2.rpms):
                if be_verbose:
                    util.write_out(self.two_col.format(r, r))
            elif (r in self.i1.rpms) and not (r in self.i2.rpms):
                util.write_out(self.two_col.format(r, ""))
            elif not (r in self.i1.rpms) and (r in self.i2.rpms):
                util.write_out(self.two_col.format("", r))

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
            util.write_out(self.two_col.format(col1, col2))

    def rpm_json(self):
        """
        Pretty prints the output in json format
        :return: None
        """
        def _form_image_json(image, exclusive, common):
            return {
                "release": image.release,
                "all_rpms": image.rpms,
                "unique_rpms": exclusive,
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
    def __init__(self, image_list):
        #self.compare = dircmp(chroot_left, chroot_right)
        self.img_left, self.img_right = (x for x in image_list)
        self.left = []
        self.right = []
        self.common_diff = []
        self.chroot_left = []
        self.chroot_right =[]
        self.parse_mtree_json()

    def parse_mtree_json(self):
        def extra(_result): #pylint: disable=unused-variable
            self.right.append(_result['path'])

        def missing(_result): #pylint: disable=unused-variable
            self.left.append(_result['path'])

        def modified(_result): #pylint: disable=unused-variable
            self.common_diff.append({'path': _result['path'], 'reasons': sorted(key['name'] for key in _result['keys'])})

        for result in self.img_right.validation_result:
            func = eval(result['type']) #pylint: disable=eval-used
            func(result)

    def get_only(self, _chroot):
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
                if isinstance(_file, dict):
                    util.write_out("{0}{1} ({2})".format(5*" ", _file['path'], " ".join(_file['reasons'])))
                else:
                    util.write_out("{0}{1}".format(5*" ", _file))

        if all([len(self.left) == 0, len(self.right) == 0,
                len(self.common_diff) == 0]):
            util.write_out("\nThere are no file differences between {0} "
                          "and {1}".format(left_docker_obj, right_docker_obj))
        if len(self.left) > 0:
            util.write_out("\nFiles only in {}:".format(left_docker_obj))
            _print_diff(self.left)
        if len(self.right) > 0:
            util.write_out("\nFiles only in {}:".format(right_docker_obj))
            _print_diff(self.right)
        if len(self.common_diff):
            util.write_out("\nCommon files that are different: (reason)")
            _print_diff(self.common_diff)


class CompareMetaData(object):

    def __init__(self, images):
        self.img_obj1, self.img_obj2 = (x for x in images)
        # Only two images can be in the list, so this OK
        self.image1_metadata, self.image2_metadata = (x.inspect_data for x in images)
        self.good_values = []

    def walk_dict(self, image1, image2, parents=None):
        if not parents:
            parents = []
        try:
            if image1 == self.get_node_value(image2, parents):
                self.good_values.append(parents)
                return
        except NoKey:
            pass
        for k, v in image1.items():
            if isinstance(v, dict):
                _parents = parents + [k]
                self.walk_dict(v, image2, parents=_parents)
            elif isinstance(v, list):
                _parents = parents + [k]
                self.walk_list(v, image2, _parents)
            else:
                try:
                    image2_value = self.get_node_value(image2, parents + [k])
                    if v == image2_value:
                        # delete
                        self.good_values.append(parents + [k])
                except NoKey:
                    pass

    @staticmethod
    def get_node_value(image, parents):
        def _get_node(image, get_val):
            try:
                _ = iter(image)
                if get_val in image:
                    return image.get(get_val)
            except TypeError:
                pass

            raise NoKey
        node = image
        for parent in parents:
            node = _get_node(node, parent)
        return node

    @staticmethod
    def set_node_value(image, parents, new_value):
        last_key = parents[-1]
        for key in parents:
            if key == last_key:
                if key in image:
                    image[key] = new_value
            else:
                image = image.get(key)

    @staticmethod
    def del_node_value(parents, image):
        last_key = parents[-1]
        for key in parents:
            if key == last_key:
                if key in image:
                    del image[key]
            else:
                image = image.get(key)

    def walk_list(self, image1, image2, parents):
        try:
            image2 = self.get_node_value(image2, parents)
            # Need to account for docker versions that insert a None|null
            # instead of an empty list
            if image1 is None:
                image1 = []
            if image2 is None:
                image2 = []
            # In docker inspects, not allowed to have dicts|lists inside lists
            # In image1, not 2
            image1_uniq = list(set(image1).difference(set(image2)))
            # In image2, not 1
            image2_uniq = list(set(image2).difference(set(image1)))
            if not image1_uniq and not image2_uniq:
                self.good_values.append(parents)
        except NoKey:
            pass

    def compare(self):
        image1 = self.image1_metadata
        image2 = self.image2_metadata
        self.walk_dict(self.image1_metadata, self.image2_metadata, parents=[])
        self.walk_dict(self.image2_metadata, self.image1_metadata, parents=[])
        for i in self.good_values:
            if not i:
                image1.clear()
                image2.clear()
                break
            self.del_node_value(i, image1)
            self.del_node_value(i, image2)
        self.img_obj1.metadata_results = image1
        self.img_obj2.metadata_results = image2


class NoKey(Exception):
    pass
