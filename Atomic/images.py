from Atomic import Atomic
from Atomic import util
from Atomic import info
from Atomic import update
from Atomic import verify
from Atomic import help as Help
from Atomic.mount import Mount
from Atomic.delete import Delete
from Atomic.tag import Tag
import os
import math
import shutil
import tempfile
import argparse
from Atomic import backendutils

ATOMIC_CONFIG = util.get_atomic_config()
storage = ATOMIC_CONFIG.get('default_storage', "docker")

def convert_size(size):
    if size > 0:
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = int(math.floor(math.log(size, 1000)))
        p = math.pow(1000, i)
        s = round(size/p, 2) # pylint: disable=round-builtin,old-division
        if s > 0:
            return '%s %s' % (s, size_name[i])
    return '0B'

def cli(subparser):
    # atomic images
    imagesp = subparser.add_parser("images",
                                   help=_("operate on images"))
    images_subparser = imagesp.add_subparsers(title='images subcommands',
                                              description="operate on images",
                                              help='additional help')

    # atomic images delete
    delete_parser = images_subparser.add_parser("delete",
                                                help=_("mark image for deletion"),
                                                epilog="Marks image. registry garbage-collection "
                                                "when invoked will recover used disk space")

    deletegroup = delete_parser.add_mutually_exclusive_group()
    deletegroup.add_argument("-f", "--force", default=False, dest="force",
                             action="store_true",
                             help=_("Force removal of local images, even if containers based on it exist.  Default is False"))

    deletegroup.add_argument("--remote", default=False, dest="remote",
                             action="store_true",
                             help=_("Delete image from remote repository"))

    delete_parser.add_argument("--storage", default=None, dest="storage",
                               help=_("Specify the storage from which to delete the image from. "
                                      "If not specified and there are images with the same name in "
                                      "different storages, you will be prompted to specify."))
    delete_parser.add_argument("-a", "--all", action='store_true',dest="all",
                               default=False, help=_("Delete all images"))
    delete_parser.add_argument("delete_targets", nargs='*',
                                    help=_("container image(s)"))
    delete_parser.set_defaults(_class=Delete, func='delete_image')

    if util.gomtree_available():
        generate_parser = images_subparser.add_parser("generate",
                                                  help=_("generate image 'manifests' if missing"))
        generate_parser.set_defaults(_class=Images, func='generate_validation_manifest')

        # Suppress storage flag: only docker images are supported for generate
        generate_parser.add_argument("--storage", default=storage, dest="storage",
                                     help=argparse.SUPPRESS)

    Help.cli(images_subparser)

    info.cli(images_subparser)

    # atomic images list
    list_parser = images_subparser.add_parser("list",
                                              help=_("list container images on your system"),
                                              epilog="atomic images by default will list all installed "
                                                     "container images on your system.")
    list_parser.set_defaults(_class=Images, func='display_all_image_info')

    list_parser.add_argument("-a", "--all", dest="all", default=False,
                             action="store_true",
                             help=_("Show all images, including intermediate images"))

    list_parser.add_argument("-f", "--filter", dest="filter", metavar="FILTER",
                             action="append",
                             help=_("Filter output based on VARIABLE=VALUE format"))

    list_parser.add_argument("-n", "--noheading", dest="heading", default=True,
                             action="store_false",
                             help=_("do not print heading when listing the images"))

    list_parser.add_argument("--no-trunc", dest="truncate", default=True,
                             action="store_false",
                             help=_("Don't truncate output"))

    list_parser.add_argument("-q", "--quiet", dest="quiet", default=False,
                             action="store_true",
                             help=_("Only display image IDs"))
    list_parser.add_argument("--json", action='store_true',dest="json", default=False,
                             help=_("print in a machine parseable form"))

    # atomic images tag
    tag_parser = images_subparser.add_parser("tag",
                                                help=_("Create a tag for the specified image"),
                                                epilog="Tag the specified image with a different name")
    tag_parser.add_argument("--storage", default=None, dest="storage",
                               help=_("Specify the storage to use for tagging the image. "
                                      "If not specified and there are images with the same name in "
                                      "different storages, you will be prompted to specify."))
    tag_parser.add_argument('src', metavar='SRC')
    tag_parser.add_argument('target', metavar='TARGET')

    tag_parser.set_defaults(_class=Tag, func='tag_image')

    prune_parser = images_subparser.add_parser("prune",
                                               help=_("delete unused 'dangling' images"),
                                               epilog="Using the prune command, "
                                                      "will free up disk space deleting unused "
                                                      "'dangling' images")
    prune_parser.set_defaults(_class=Delete, func='prune_images')

    update.cli(images_subparser)

    verify.cli(images_subparser)

    info.cli_version(images_subparser)

class Images(Atomic):

    FILTER_KEYWORDS = ["repo", "repository", "tag", "id", "image", "created", "size", "type", "is_dangling"]

    def __init__(self):
        super(Images, self).__init__()
        self.be_utils = backendutils.BackendUtils()

    def display_all_image_info(self):
        def get_col_lengths(_images):
            '''
            Determine the max length of the repository and tag names
            :param _images:
            :return: a set with len of repository and tag
            If there are no images, return 1, 1
            '''
            repo_tags = [y for x in _images if x.repotags for y in x.split_repotags]

            if repo_tags:
                return max([len(x[0]) for x in repo_tags]) + 2,\
                       max([len(x[1]) for x in repo_tags]) + 2
            else:
                return 1, 1

        if self.args.debug:
            util.write_out(str(self.args))
            self.be_utils.dump_backends()

        _images = self._get_images()

        if self.args.filter:
            self._check_filter_validity()

        if self.args.json:
            util.output_json(self.return_json(_images))
            return 0

        if len(_images) == 0:
            return

        _max_repo, _max_tag = get_col_lengths(_images)

        if self.args.truncate:
            _max_id = 14
        else:
            _max_id = 65
        col_out = "{0:2} {1:" + str(_max_repo) + "} {2:" + str(_max_tag) + \
                  "} {3:" + str(_max_id) + "} {4:18} {5:14} {6:10}"

        if self.args.heading and not self.args.quiet:
            util.write_out(col_out.format(" ",
                                          "REPOSITORY",
                                          "TAG",
                                          "IMAGE ID",
                                          "CREATED",
                                          "VIRTUAL SIZE",
                                          "TYPE"))
        for image in _images:
            _id = image.short_id if self.args.truncate else image.id
            if self.args.quiet:
                for _repo, _tag in image.split_repotags:
                    if self.args.filter and not self._filter_include_image(image, _repo, _tag):
                        continue
                    util.write_out(_id)

            else:
                indicator = ""
                if image.is_dangling_cached:
                    indicator += "*"
                elif image.used:
                    indicator += ">"
                if image.vulnerable:
                    space = " " if len(indicator) < 1 else ""
                    if util.is_python2:
                        indicator = indicator + self.skull + space
                    else:
                        indicator = indicator + str(self.skull, "utf-8") + space

                for _repo, _tag in image.split_repotags:
                    if self.args.filter and not self._filter_include_image(image, _repo, _tag):
                        continue
                    util.write_out(col_out.format(indicator, _repo or "<none>", _tag or "<none>", _id, image.created[0:16],
                                                  image.virtual_size, image.backend.backend))
        return

    def _get_images(self):
        _images = self.be_utils.get_images(get_all=self.args.all)

        self._mark_used(_images)
        self._mark_vulnerable(_images)

        return _images

    def images(self):
        return self.return_json(self._get_images())


    def generate_validation_manifest(self):
        """
        Generates a gomtree validation manifest for a non-system image and stores it in
        ATOMIC_VAR_LIB
        :param:
        :return: None
        """
        _images = self.get_images(get_all=True)
        for image in _images:
            atomic_var_lib = util.ATOMIC_VAR_LIB
            if not image["RepoTags"]:
                continue
            iid = image["RepoTags"][0]
            if image["ImageType"] == "system":
                continue
            if iid == "<none>:<none>" or iid == "<none>":
                continue
            if os.path.exists(os.path.join(atomic_var_lib, "gomtree-manifests/%s.mtree" % iid)):
                continue
            manifestname = os.path.join(atomic_var_lib, "gomtree-manifests/%s.mtree" % iid)
            dname = os.path.dirname(manifestname)
            if not os.path.exists(dname):
                os.makedirs(dname)
            tmpdir = tempfile.mkdtemp()
            m = Mount()
            m.args = []
            m.image = iid
            m.mountpoint = tmpdir
            m.storage = self.args.storage
            m.mount()
            r = util.generate_validation_manifest(img_rootfs=tmpdir, keywords="type,uid,gid,mode,size,sha256digest")
            m.unmount()
            with open(manifestname,"wb",0) as f:
                f.write(r.stdout)
            shutil.rmtree(tmpdir)

    def _check_filter_validity(self):
        for i in self.args.filter:
            try:
                var, _ = str(i).split("=")
            except ValueError:
                raise ValueError("The filter {} is not formatted correctly.  It should be VAR=VALUE".format(i))

            var = var.lower()
            if var not in self.FILTER_KEYWORDS:
                raise ValueError("The filter {} is not valid.  "
                                 "Please choose from {}".format(var, self.FILTER_KEYWORDS))


    def _filter_include_image(self, image_obj, repo, tag):
        for i in self.args.filter:
            var, value = str(i).split("=")
            var = var.lower()
            if var == "repository":
                var = "repo"

            if var == "image":
                var = "id"

            if var == "type":
                var = "str_backend"

            if var == "repo":
                if not value.lower() in repo:
                    return False

            elif var == "tag":
                if not value.lower() in tag:
                    return False

            elif not hasattr(image_obj, var):
                return False

            elif hasattr(image_obj, var) and value.lower() not in str(getattr(image_obj, var)).lower():
                return False

        return True

    def _mark_used(self, images):
        assert isinstance(images, list)
        all_containers = [x.image for x in self.be_utils.get_containers()]
        for image in images:
            if image.id in all_containers:
                image.used = True

    def _mark_vulnerable(self, images):
        assert isinstance(images, list)
        vulnerable_uuids = self.get_vulnerable_ids()
        for image in images:
            if image.id in vulnerable_uuids:
                image.vulnerable = True

    def return_json(self, images):
        all_image_info = []
        all_vuln_info = self.get_all_vulnerable_info()
        keys = ['is_dangling', 'used', 'vulnerable', 'id', 'type', 'created', 'virtual_size', 'str_backend']
        keys_rename = {"str_backend" : "backend"}
        for img_obj in images:
            if not img_obj.repotags:
                continue

            for _repo, _tag in img_obj.split_repotags:
                if self.args.filter and not self._filter_include_image(img_obj, _repo, _tag):
                    continue

                img_dict = dict()
                img_dict['repo'], img_dict['tag'] = _repo, _tag
                for key in keys:
                    key_name = key if key not in keys_rename else keys_rename[key]
                    img_dict[key_name] = getattr(img_obj, key, None)
                img_dict['vuln_info'] = \
                    dict() if not img_obj.vulnerable else all_vuln_info.get(img_obj.id, None) # pylint: disable=no-member
                all_image_info.append(img_dict)

        return all_image_info


