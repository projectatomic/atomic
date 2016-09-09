try:
    from . import Atomic
except ImportError:
    from atomic import Atomic  # pylint: disable=relative-import
from .util import skopeo_copy, get_atomic_config, get_atomic_config_item, skopeo_inspect, decompose, write_out, write_registry_config, install_pubkey, update_trust_policy

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
    pullp.add_argument("image", help=_("image id"))


class Pull(Atomic):
    def pull_docker_image(self):
        _, _, tag = decompose(self.args.image)
        # If no tag is given, we assume "latest"
        tag = tag if tag != "" else "latest"
        fq_name = skopeo_inspect("docker://{}".format(self.args.image))['Name']
        image = "docker-daemon:{}:{}".format(fq_name, tag)
        if get_atomic_config_item(['discover_sigstores'], get_atomic_config()):
            if not self.discover_sigstore():
                write_out("There was a problem configuring the trust policy")
        skopeo_copy("docker://{}".format(self.args.image), image, debug=self.args.debug)

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

    def discover_sigstore(self):
        """
        Check for registry/repo/sigstore metadata image
        prompt user for trust on first use workflow
        :return: True if sigstore discovered and configured
        """
        (registry, repo, _) = decompose(self.args.image)
        # FIXME: this should be handled in util.decompose
        _repo, _image = repo.split('/')
        # TODO: check local /etc/containers/registries.d config here
        repo_sigstore_labels = self._get_sigstore_image_metadata(registry, _repo)
        if self._validate_sigstore_labels(repo_sigstore_labels):
            if self._prompt_trust(repo_sigstore_labels):
                discover_config = False
                trust_scope = "%s/%s" % (registry, _repo)
                discover_config = write_registry_config(trust_scope)
                pubkey_path = install_pubkey(repo_sigstore_labels['pubkey-id'], repo_sigstore_labels['pubkey-url'])
                discover_config = update_trust_policy(trust_scope, pubkey_path, repo_sigstore_labels['sigstore-url'])
                return discover_config
        return False

    def _get_sigstore_image_metadata(self, registry, repo):
        """
        Get sigstore metadata image
        :param registry: registry string
        :param repo: repo string
        :return True on success
        """
        _img = get_atomic_config_item(['sigstore_metadata_image'], get_atomic_config())
        sigstoreimage = '/'.join([registry, repo, _img])
        data = skopeo_inspect("docker://" + sigstoreimage, args=None, fail_silent=True)
        if data:
            write_out("Found registry sigstore metadata image %s" % sigstoreimage)
            return data['Labels']
        else:
            return False

    def _validate_sigstore_labels(self, labels):
        """
        Validate sigstore metadata.
        If there's a missing key or something we don't want to perform any automatic trust policy configuration
        :param labels: unvalidated labels. Should be either dict or False
        :return: True if labels are valid
        """
        valid = False
        if labels:
            expected_keys = ["pubkey-id", "pubkey-fingerprint", "pubkey-url", "sigstore-url", "sigstore-type"]
            for k in expected_keys:
                valid = k in labels
        return valid

    def _prompt_trust(self, labels):
        """
        Prompt user for trust on first use workflow
        :param labels: dict of metadata labels defining sigstore trust
        :return: True if user accepts
        """
        write_out("ID: " + labels['pubkey-id'])
        write_out("Fingerprint: " + labels['pubkey-fingerprint'])
        write_out("Public key download URL: %s" % labels['pubkey-url'])
        confirm = None
        if self.args.assumeyes:
            confirm = "yes"
        else:
            confirm = util.input("Do you want to add trust policy for this registry? (y/N)")
        if not "y" in confirm.lower():
            return False
        return True

