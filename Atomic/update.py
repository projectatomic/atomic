try:
    from . import Atomic
except ImportError:
    from atomic import Atomic # pylint: disable=relative-import

import argparse
from Atomic.backendutils import BackendUtils
from Atomic.util import get_atomic_config, write_out, write_err, Decompose
import sys

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
    updatep.add_argument("-a", "--all", default=False, dest="all",
                         action="store_true",
                         help=_("update all the images"))
    updatep.add_argument("--storage", default=None, dest="storage",
                         help=_("Specify the storage of the image. Defaults to: %s" % storage))
    updatep.add_argument("image", nargs='?', help=_("container image"))

class Update(Atomic):
    def __init__(self): # pylint: disable=useless-super-delegation
        super(Update, self).__init__()

    def update_all_images(self, be, debug):
        images = be.get_images()
        images_by_name = {}
        for i in images:
            if i.repotags is None:
                continue

            img_name = i.repotags[0]
            d = Decompose(img_name)
            if d.registry == "":
                write_err("Image {} not fully qualified: skipping".format(img_name))
                continue

            images_by_name[img_name] = i
            could_not_pull = {}
            pulled = {}

            write_out("Checking image {}...".format(img_name))
            try:
                be.update(img_name, debug=debug, force=False, image_object=i)
                pulled[img_name] = True
            except:  # pylint: disable=bare-except
                could_not_pull[img_name] = True

        def get_status(img_name, pre_id, post_id):
            COLOR_RED = 31
            COLOR_GREEN = 32

            if img_name in could_not_pull.keys():
                return "Could not pull", COLOR_RED

            if pre_id != post_id:
                return "Updated now", COLOR_GREEN

            return "Updated", COLOR_GREEN

        def colored(line, color):
            if sys.stdout.isatty():
                return "\x1b[1;%dm%s\x1b[0m" % (color, line)
            else:
                return line

        cols = "{0:50} {1:32} {2:32} {3:15}"

        write_out("\nSUMMARY\n")
        write_out(cols.format("Image", "Image ID before update", "Image ID after update", "Status"))
        for k, v in images_by_name.items():
            new_image = be.inspect_image(k)
            status, color = get_status(k, v.id, new_image.id)
            colored_status = colored(status[:15], color)
            write_out(cols.format(k[:50], v.id[:32], new_image.id[:32], colored_status))

    def update(self):
        if self.args.debug:
            write_out(str(self.args))

        if self.args.all and self.args.image is not None:
            raise ValueError("Cannot specify both --all and an image name")

        if self.args.all and self.args.force:
            raise ValueError("Cannot specify both --all and --force")

        if self.args.all and self.args.storage is None:
            raise ValueError("Please specify --storage")

        beu = BackendUtils()

        if self.args.all:
            be = beu.get_backend_from_string(self.args.storage)
            return self.update_all_images(be, self.args.debug)

        try:
            be, img_obj = beu.get_backend_and_image_obj(self.image, str_preferred_backend=self.args.storage or storage, required=True if self.args.storage else False)
            input_name = img_obj.input_name
        except ValueError:
            raise ValueError("{} not found locally.  Unable to update".format(self.image))

        be.update(input_name, debug=self.args.debug, force=self.args.force, image_object=img_obj)
        return 0
