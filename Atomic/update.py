try:
    from . import Atomic
except ImportError:
    from atomic import Atomic # pylint: disable=relative-import

import argparse
from Atomic.backendutils import BackendUtils
from Atomic.util import get_atomic_config, write_out

ATOMIC_CONFIG = get_atomic_config()
storage = ATOMIC_CONFIG.get('default_storage', "docker")

def cli(subparser, hidden=False):
    # atomic update
    if hidden:
        updatep = subparser.add_parser("update", argument_default=argparse.SUPPRESS)
    else:
        updatep = subparser.add_parser(
            "update", help=_("pull latest container image from repository"),
            epilog="downloads the latest container image. If a previously created "
            "container based on this image exists, the container will "
            "continue to use the old image.  Use --force to remove the "
            "outdated container.")
    updatep.set_defaults(_class=Update, func='update')
    updatep.add_argument("-f", "--force", default=False, dest="force",
                         action="store_true",
                         help=_("remove all containers based on this image"))
    updatep.add_argument("--storage", default=None, dest="storage",
                         help=_("Specify the storage of the image. Defaults to: %s" % storage))
    updatep.add_argument("image", help=_("container image"))

class Update(Atomic):
    def __init__(self):
        super(Update, self).__init__()

    def update(self):
        if self.args.debug:
            write_out(str(self.args))
        beu = BackendUtils()
        try:
            be, img_obj = beu.get_backend_and_image_obj(self.image, str_preferred_backend=self.args.storage or storage, required=True if self.args.storage else False)
            input_name = img_obj.input_name
        except ValueError:
            raise ValueError("{} not found locally.  Unable to update".format(self.image))
        be.update(input_name, debug=self.args.debug, force=self.args.force, image_object=img_obj)
        return 0
