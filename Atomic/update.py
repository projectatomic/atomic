try:
    from . import Atomic
except ImportError:
    from atomic import Atomic # pylint: disable=relative-import

from .syscontainers import OSTREE_PRESENT

def cli(subparser):
    # atomic update
    updatep = subparser.add_parser(
        "update", help=_("pull latest container image from repository"),
        epilog="atomic update downloads the latest container image. If a "
        "previously created  container based on this image exists, "
        "the container will continue to use the old image.  Use "
        "--force to remove the outdated container.")
    updatep.set_defaults(_class=Update, func='update')
    updatep.add_argument("-f", "--force", default=False, dest="force",
                         action="store_true",
                         help=_("remove all containers based on this image"))
    if OSTREE_PRESENT:
        updatep.add_argument("--set", dest="setvalues",
                             action='append',
                             help=_("Specify a variable in the VARIABLE=VALUE "
                                    "form for a system container"))
    updatep.add_argument("--container", dest="container",
                         action='store_true', default=False,
                         help=_('update an installed container'))
    updatep.add_argument("image", help=_("container image"))

class Update(Atomic):
    def __init__(self):
        super(Update, self).__init__()

    def update(self):
        super(Update, self).update()
