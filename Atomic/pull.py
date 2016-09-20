try:
    from . import Atomic
except ImportError:
    from atomic import Atomic  # pylint: disable=relative-import
from .trust import Trust
from .util import skopeo_copy, get_atomic_config, skopeo_inspect,\
    decompose, write_out, strip_port, is_insecure_registry

ATOMIC_CONFIG = get_atomic_config()


def cli(subparser):
    # atomic pull
    backend = ATOMIC_CONFIG.get('default_storage', "ostree")
    pullp = subparser.add_parser("pull", help=_("pull latest image from a repository"),
                                 epilog="pull the latest specified image from a repository.")
    pullp.set_defaults(_class=Pull, func='pull_image')
    pullp.add_argument("--storage", dest="backend", default=backend,
                       help=_("Specify the storage. Default is currently '%s'.  You can"
                              " change the default by editing /etc/atomic.conf and changing"
                              " the 'default_storage' field." % backend))
    pullp.add_argument("-t", "--type", dest="reg_type", default=None,
                       help=_("Pull from an alternative registry type."))
    pullp.add_argument("image", help=_("image id"))


class Pull(Atomic):
    def pull_docker_image(self):
        registry, _, tag = decompose(self.args.image)
        insecure = True if is_insecure_registry(self.d.info()['RegistryConfig'], strip_port(registry)) else False
        # If no tag is given, we assume "latest"
        tag = tag if tag != "" else "latest"
        if self.args.reg_type == "atomic":
            pull_uri = 'atomic:'
        else:
            pull_uri = 'docker://'
        fq_name = skopeo_inspect("{}{}".format(pull_uri, self.args.image))['Name']
        image = "docker-daemon:{}:{}".format(fq_name, tag)
        trust = Trust()
        trust.set_args(self.args)
        trust.discover_sigstore(fq_name)
        skopeo_copy("docker://{}".format(self.args.image), image, debug=self.args.debug, insecure=insecure)

    def pull_image(self):
        handlers = {
            "ostree" : self.syscontainers.pull_image,
            "docker" : self.pull_docker_image
        }

        handler = handlers.get(self.args.backend)
        if handler is None:
            raise ValueError("Destination not known, please choose --storage=%s" % "|".join(handlers.keys()))
        write_out("Image %s is being pulled to %s ..." % (self.args.image, self.args.backend))
        handler()

