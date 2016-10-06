from . import util

try:
    from . import Atomic
except ImportError:
    from atomic import Atomic # pylint: disable=relative-import

from .atomic import AtomicError

def cli(subparser):
    # atomic info
    infop = subparser.add_parser(
        "info", help=_("display label information about an image"),
        epilog="atomic info attempts to read and display the LABEL "
        "information about an image")
    infop.set_defaults(_class=Info, func='info_tty')
    infop.add_argument("--remote", dest="force",
                       action='store_true', default=False,
                       help=_('ignore local images and only scan registries'))
    infop.add_argument("image", help=_("container image"))

def cli_version(subparser):
    # atomic version
    versionp = subparser.add_parser(
        "version", help=_("display image 'Name Version Release' label"),
        epilog="atomic version displays the image version information, if "
        "it is provided")
    versionp.add_argument("-r", "--recurse", default=False, dest="recurse",
                          action="store_true",
                          help=_("recurse through all layers"))
    versionp.set_defaults(_class=Info, func='version')
    versionp.add_argument("image", help=_("container image"))


class Info(Atomic):
    def __init__(self):
        super(Info, self).__init__()

    def version(self):
        self.args.force = False
        self.info_tty()

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
            #pylint: disable=unexpected-keyword-arg
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
        for layer in self.version():
            version = layer["Version"]
            if layer["Version"] == '':
                version = "None"
            util.write_out("%s %s %s" % (layer["Id"], version, layer["Tag"]))
