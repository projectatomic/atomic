from . import util
import argparse

try:
    from . import Atomic
except ImportError:
    from atomic import Atomic  # pylint: disable=relative-import

from Atomic.util import get_atomic_config
from Atomic.backendutils import BackendUtils
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from contextlib import closing
from Atomic.discovery import RegistryInspectError

ATOMIC_CONFIG = get_atomic_config()
storage = ATOMIC_CONFIG.get('default_storage', "docker")

def cli(subparser, hidden=False):
    # atomic info
    if hidden:
        infop = subparser.add_parser("info", argument_default=argparse.SUPPRESS)

    else:
        infop = subparser.add_parser(
            "info", help=_("display label information about an image"),
            epilog="atomic info attempts to read and display the LABEL "
            "information about an image")

    infop.set_defaults(_class=Info, func='info_tty')
    infop.add_argument("--remote", dest="force",
                       action='store_true', default=False,
                       help=_('ignore local images and only scan registries'))
    infop.add_argument("--storage", default=None, dest="storage",
                       help=_("Specify the storage of the image. "
                              "If not specified and there are images with the same name in "
                              "different storages, you will be prompted to specify."))
    infop.add_argument("image", help=_("container image"))


def cli_version(subparser, hidden=False):
    if hidden:
        versionp = subparser.add_parser("version", argument_default=argparse.SUPPRESS)

    else:
        versionp = subparser.add_parser(
            "version", help=_("display image 'Name Version Release' label"),
            epilog="atomic version displays the image version information, if "
            "it is provided")
    versionp.add_argument("-r", "--recurse", default=False, dest="recurse",
                          action="store_true",
                          help=_("recurse through all layers"))
    versionp.add_argument("--storage", default=None, dest="storage",
                          help=_("Specify the storage of the image. "
                                 "If not specified and there are images with the same name in "
                                 "different storages, you will be prompted to specify."))
    versionp.set_defaults(_class=Info, func='version')
    versionp.add_argument("image", help=_("container image"))


class Info(Atomic):
    def __init__(self):
        super(Info, self).__init__()
        self.beu = BackendUtils()

    def version(self):
        self._version(util.write_out)

    def _version(self, write_func):
        layer_objects = self.get_layer_objects()
        max_version_len = max([len(x.long_version) for x in layer_objects])
        max_version_len = max_version_len if max_version_len > 9 else 9
        max_img_len = len(max([y for x in layer_objects for y in x.repotags], key=len)) + 9
        max_img_len = max_img_len if max_img_len > 12 else 12
        col_out = "{0:" + str(max_img_len) + "} {1:" + str(max_version_len) + "} {2:10}"

        write_func(col_out.format("IMAGE NAME", "VERSION", "IMAGE ID"))
        for layer in layer_objects:
            for int_img_name in range(len(layer.repotags)):
                version = layer.long_version if int_img_name < 1 else ""
                iid = layer.id[:12] if int_img_name < 1 else ""
                space = "" if int_img_name < 1 else "  Tag: "
                write_func(col_out.format(space + layer.repotags[int_img_name], version, iid))
                write_func("")

    def get_layer_objects(self):
        _, img_obj = self.beu.get_backend_and_image_obj(self.image, str_preferred_backend=self.args.storage or storage, required=True if self.args.storage else False)
        return img_obj.layers

    def dbus_version(self):
        layer_objects = self.get_layer_objects()
        versions = []
        for layer in layer_objects:
            versions.append({"Image": layer.repotags, "Version": layer.long_version, "iid": layer.id})
        return versions

    def info_tty(self):
        if self.args.debug:
            util.write_out(str(self.args))
        util.write_out(self.info())

    def info(self):
        """
        Retrieve and print all LABEL information for a given image.
        """

        if self.args.storage == 'ostree' and self.args.force:
            # Ostree and remote combos are illegal
            raise ValueError("The --remote option cannot be used with the 'ostree' storage option.")

        if self.args.force:
            # The user wants information on a remote image
            be = self.beu.get_backend_from_string(str_backend=self.args.storage or storage)
            img_obj = be.make_remote_image(self.image)
        else:
            # The image is local
            be, img_obj = self.beu.get_backend_and_image_obj(self.image, str_preferred_backend=self.args.storage or storage, required=True if self.args.storage else False)

        with closing(StringIO()) as buf:
            try:
                info_name = img_obj.fq_name
            except RegistryInspectError:
                info_name = img_obj.input_name
            buf.write("Image Name: {}\n".format(info_name)) # pylint: disable=no-member
            if img_obj.labels:
                buf.writelines(sorted(["{}: {}\n".format(k, v) for k,v in list(img_obj.labels.items())])) # pylint: disable=no-member
            if img_obj.template_variables_set:
                buf.write("\n\nTemplate variables with default value, but overridable with --set:\n") # pylint: disable=no-member
                buf.writelines(["{}: {}\n".format(k, v) for k,v in   # pylint: disable=no-member
                                list(sorted(img_obj.template_variables_set.items()))])
            if img_obj.template_variables_unset:
                buf.write("\n\nTemplate variables that has no default value, and must be set with --set:\n") # pylint: disable=no-member
                buf.writelines(["{}: {}\n".format(k, v) for k,v in   # pylint: disable=no-member
                                list(sorted(img_obj.template_variables_unset.items()))])
            return buf.getvalue() # pylint: disable=no-member


