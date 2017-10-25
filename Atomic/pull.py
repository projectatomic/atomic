try:
    from . import Atomic
except ImportError:
    from atomic import Atomic  # pylint: disable=relative-import
from .util import get_atomic_config, write_out, check_storage_is_available
from Atomic.backendutils import BackendUtils

ATOMIC_CONFIG = get_atomic_config()


_storage = ATOMIC_CONFIG.get('default_storage', "docker")

def cli(subparser):
    # atomic pull
    pullp = subparser.add_parser("pull", help=_("pull latest image from a repository"),
                                 epilog="pull the latest specified image from a repository.")
    pullp.set_defaults(_class=Pull, func='pull_image')
    pullp.add_argument("--storage", dest="storage", default=None,
                       help=_("Specify the storage. Default is currently '%s'.  You can"
                              " change the default by editing /etc/atomic.conf and changing"
                              " the 'default_storage' field." % _storage))
    pullp.add_argument("--src-creds", dest="src_creds", default=None,
                       help=_("Use USERNAME[:PASSWORD] for accessing the source registry."))
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
        storage_set = False if self.args.storage is None else True
        storage = _storage if not storage_set else self.args.storage
        check_storage_is_available(storage)
        if self.args.debug:
            write_out(str(self.args))

        src_creds = getattr(self.args, 'src_creds', None)
        if src_creds == "":
            src_creds = None

        be_utils = BackendUtils()
        be = be_utils.get_backend_from_string(storage)
        self.args.policy_filename = self.policy_filename
        try:
            if be.backend == 'docker':
                remote_image_obj = be.make_remote_image(self.args.image)
                if remote_image_obj.is_system_type and not storage_set:
                    be = be_utils.get_backend_from_string('ostree')
                    be_utils.message_backend_change('docker', 'ostree')
            elif be.backend == "containers-storage":
                remote_image_obj = be.make_remote_image(self.args.image)
            else:
                remote_image_obj = None
            be.pull_image(self.args.image, remote_image_obj, debug=self.args.debug, assumeyes=self.args.assumeyes, src_creds=src_creds)
        except ValueError as e:
            raise ValueError("Failed: {}".format(e))
        return 0


