try:
    from . import Atomic
except ImportError:
    from atomic import Atomic  # pylint: disable=relative-import
from .trust import Trust
from .util import skopeo_copy, get_atomic_config, Decompose, write_out, strip_port, is_insecure_registry

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

    def pull_docker_image(self):
        self.ping()
        # Add this when atomic registry is incorporated.
        # if self.args.reg_type == "atomic":
        #     pull_uri = 'atomic:'
        # else:
        #     pull_uri = 'docker://'
        if self.args.image.startswith("dockertar:"):
            path = self.args.image.replace("dockertar:", "", 1)
            with open(path, 'rb') as f:
                self.d.load_image(data=f)
        else: # assume decomposable fqin
            fq_name = self.get_fq_image_name(self.args.image)
            registry, _, _, tag, _ = Decompose(fq_name).all
            image = "docker-daemon:{}".format(self.args.image)
            if not self.args.image.endswith(tag):
                image += ":{}".format(tag)
            insecure = True if is_insecure_registry(self.d.info()['RegistryConfig'], strip_port(registry)) else False
            trust = Trust()
            trust.set_args(self.args)
            trust.discover_sigstore(fq_name)
            write_out("Pulling {} ...".format(fq_name))
            skopeo_copy("docker://{}".format(fq_name), image,
                        debug=self.args.debug, insecure=insecure,
                        policy_filename=self.policy_filename)

    def pull_image(self):
        handlers = {
            "ostree" : self.syscontainers.pull_image,
            "docker" : self.pull_docker_image
        }

        handler = handlers.get(self.args.storage)
        if handler is None:
            raise ValueError("Destination not known, please choose --storage=%s" % "|".join(handlers.keys()))
        write_out("Image %s is being pulled to %s ..." % (self.args.image, self.args.storage))
        handler()
