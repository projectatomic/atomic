import argparse
from . import util
from .util import add_opt
from .install import INSTALL_ARGS
from Atomic.backendutils import BackendUtils
import sys
from Atomic.backends._ostree import OSTreeBackend

try:
    from . import Atomic
except ImportError:
    from atomic import Atomic # pylint: disable=relative-import

ATOMIC_CONFIG = util.get_atomic_config()
_storage = ATOMIC_CONFIG.get('default_storage', "docker")

def cli(subparser):
    # atomic uninstall
    uninstallp = subparser.add_parser(
        "uninstall", help=_("execute container image uninstall method"),
        epilog="atomic uninstall attempts to read the LABEL UNINSTALL "
        "field in the image, if it does not exist atomic will "
        "remove the image from your machine.  You could add a "
        "LABEL UNINSTALL command to your Dockerfile like: 'LABEL "
        "UNINSTALL %s'" % Uninstall.print_uninstall())
    uninstallp.set_defaults(_class=Uninstall, func='uninstall')
    add_opt(uninstallp)
    uninstallp.add_argument("-n", "--name", dest="name", default=None,
                            help=_("name of container"))
    uninstallp.add_argument("-f", "--force", default=False, dest="force",
                            action="store_true",
                            help=_("remove all containers based on this "
                                   "image"))
    uninstallp.add_argument("--display", default=False, action="store_true",
                            help=_("preview the command that %s would execute") % sys.argv[0])
    uninstallp.add_argument("image", help=_("container image"))
    uninstallp.add_argument("--storage", dest="storage", default=None,
                            help=_("Specify the storage. Default is currently '%s'.  You can change the default "
                                   "by editing /etc/atomic.conf and changing the 'default_storage' field." % _storage))
    uninstallp.add_argument("args", nargs=argparse.REMAINDER,
                            help=_("Additional arguments appended to the "
                                   "image uninstall method"))

class Uninstall(Atomic):
    def __init__(self): # pylint: disable=useless-super-delegation
        super(Uninstall, self).__init__()

    def uninstall(self):
        if self.args.debug:
            util.write_out(str(self.args))

        beu = BackendUtils()
        try:
            be, img_obj = beu.get_backend_and_image_obj(self.args.image, str_preferred_backend=self.args.storage)
        except ValueError as e:
            if 'ostree' in [x().backend for x in beu.available_backends]:
                ost = OSTreeBackend()
                img_obj = ost.has_container(self.args.image)
                if not img_obj:
                    raise ValueError(e)
                be = ost
        be.uninstall(img_obj, name=self.args.name, atomic=self, ignore=self.args.ignore)
        return 0


    @staticmethod
    def print_uninstall():
        return "%s %s %s" % (util.default_docker(), " ".join(INSTALL_ARGS), "/usr/bin/UNINSTALLCMD")

