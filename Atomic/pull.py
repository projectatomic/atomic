try:
    from . import Atomic
except ImportError:
    from atomic import Atomic  # pylint: disable=relative-import
from .util import skopeo_copy, get_atomic_config, skopeo_inspect, decompose

ATOMIC_CONFIG = get_atomic_config()


def cli(subparser):
    # atomic pull
    backend = ATOMIC_CONFIG.get('default_storage', "ostree")
    pullp = subparser.add_parser("pull", help=_("pull latest image from a repository"),
                                 epilog="pull the latest specified image from a repository.")
    pullp.set_defaults(_class=Pull, func='pull_image')
    pullp.add_argument("--storage", dest="backend", default=backend,
                       help=_("Specify the storage. Default is currently '%s'.  You can"
                              "change the default by editing /etc/atomic.conf and changing"
                              "the 'default_storage' field." % backend))
    pullp.add_argument("image", help=_("image id"))


class Pull(Atomic):
    def pull_image(self):
        if self.args.backend == 'ostree':
            return self.syscontainers.pull_image()
        _, _, tag = decompose(self.args.image)
        # If no tag is given, we assume "latest"
        tag = tag if tag != "" else "latest"
        fq_name = skopeo_inspect("docker://{}".format(self.args.image))['Name']
        image = "docker-daemon:{}:{}".format(fq_name, tag)
        skopeo_copy("docker://{}".format(self.args.image), image)

