try:
    from . import Atomic
except ImportError:
    from atomic import Atomic  # pylint: disable=relative-import
from .util import get_atomic_config, write_out
from Atomic.backendutils import BackendUtils

ATOMIC_CONFIG = get_atomic_config()


def cli(subparser):
    # atomic pull
    storage = ATOMIC_CONFIG.get('default_storage', "docker")
    pullp = subparser.add_parser("pull", help=_("pull latest image from a repository"),
                                 epilog="pull the latest specified image from a repository.")
    pullp.set_defaults(_class=Pull, func='pull_image')
    pullp.add_argument("--storage", dest="storage", default=storage,
                       help=_("Specify the storage. Default is currently '%s'.  You can"
                              " change the default by editing /etc/atomic.conf and changing"
                              " the 'default_storage' field." % storage))
    pullp.add_argument("-t", "--type", dest="reg_type", default=None,
                       help=_("Pull from an alternative registry type."))
    pullp.add_argument("image", help=_("image id"))


class Pull(Atomic):
    def __init__(self, policy_filename=None):
        """
        :param policy_filename: override policy filename
        """
        super(Pull, self).__init__()
        self.policy_filename=policy_filename
        self.be_utils = BackendUtils()

    def pull_image(self):
        if self.args.debug:
            write_out(str(self.args))

        be = self.be_utils.get_backend_from_string(self.args.storage)
        self.args.policy_filename = self.policy_filename
        try:
            be.pull_image(self.args.image, debug=self.args.debug)
        except ValueError as e:
            write_out("Failed: {}".format(e))
            return 1
        return 0


