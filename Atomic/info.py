from . import util
import argparse

try:
    from . import Atomic
except ImportError:
    from atomic import Atomic  # pylint: disable=relative-import

from .atomic import AtomicError
from docker.errors import NotFound
import requests.exceptions

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
    versionp.set_defaults(_class=Info, func='print_version')
    versionp.add_argument("image", help=_("container image"))


class Info(Atomic):
    def __init__(self):
        super(Info, self).__init__()

    def version(self):
        is_syscon = self.syscontainers.has_image(self.image)
        try:
            self.inspect = self.d.inspect_image(self.image)
        except NotFound:
            if is_syscon:
                return self.syscontainers.version(self.image)
            self._no_such_image()
        except requests.exceptions.ConnectionError:
            if not is_syscon:
                return None
        if self.inspect and is_syscon:
            raise ValueError("There is a system container image and docker image with the same "
                             "name of '{}'. Rename or delete one of them.".format(self.image))
        if self.args.recurse:
            return self.get_layers()
        else:
            return [self._get_layer(self.image)]

    def get_version(self):
        versions = []
        for layer in self.version():
            version = "None"
            if "Version" in layer and layer["Version"] != '':
                version = layer["Version"]
            versions.append({"Image": layer['RepoTags'], "Version": version, "iid": layer['Id']})
        return versions

    def info_tty(self):
        util.write_out(self.info())

    def info(self):
        """
        Retrieve and print all LABEL information for a given image.
        """
        buf = ""

        def _no_label():
            raise ValueError("'{}' has no label information."
                             .format(self.args.image))

        # Check if the input is an image id associated with more than one
        # repotag.  If so, error out.
        if self.syscontainers.has_image(self.image):
            if not self.args.force:
                buf += ("Image Name: {}".format(self.image))
                manifest = self.syscontainers.inspect_system_image(self.image)
                labels = manifest["Labels"]
                for label in labels:
                    buf += ('\n{0}: {1}'.format(label, labels[label]))
                return buf
        elif self.is_iid():
            self.get_fq_name(self._inspect_image())
        # The input is not an image id
        else:
            try:
                iid = self._is_image(self.image)
                self.image = self.get_fq_name(self._inspect_image(iid))
            except AtomicError:
                if self.args.force:
                    self.image = util.find_remote_image(self.d, self.image)
                if self.image is None:
                    self._no_such_image()
        buf += ("Image Name: {}".format(self.image))
        inspection = None
        if not self.args.force:
            inspection = self._inspect_image(self.image)
            # No such image locally, but fall back to remote
        if inspection is None:
            # Shut up pylint in case we're on a machine with upstream
            # docker-py, which lacks the remote keyword arg.
            # pylint: disable=unexpected-keyword-arg
            inspection = util.skopeo_inspect("docker://" + self.image)
            # image does not exist on any configured registry
        if 'Config' in inspection and 'Labels' in inspection['Config']:
            labels = inspection['Config']['Labels']
        elif 'Labels' in inspection:
            labels = inspection['Labels']
        else:
            _no_label()

        if labels is not None and len(labels) is not 0:
            for label in labels:
                buf += ('\n{0}: {1}'.format(label, labels[label]))
        else:
            _no_label()
        return buf

    def print_version(self):
        versions = self.get_version()
        max_version_len = len(max([x['Version'] for x in versions], key=len)) + 2
        max_version_len = max_version_len if max_version_len > 9 else 9
        max_img_len = len(max([y for x in versions for y in x['Image']], key=len)) + 9
        max_img_len = max_img_len if max_img_len > 12 else 12
        col_out = "{0:" + str(max_img_len) + "} {1:" + str(max_version_len) + "} {2:10}"
        util.write_out("")
        util.write_out(col_out.format("IMAGE NAME", "VERSION", "IMAGE ID"))
        for layer in versions:
            for int_img_name in range(len(layer['Image'])):
                version = layer['Version'] if int_img_name < 1 else ""
                iid = layer['iid'][:12] if int_img_name < 1 else ""
                space = "" if int_img_name < 1 else "  Tag: "
                util.write_out(col_out.format(space + layer['Image'][int_img_name], version, iid))
        util.write_out("")

