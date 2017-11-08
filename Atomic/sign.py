from . import util
from . import Atomic
from . import discovery
import os
import tempfile

try:
    from urlparse import urlparse #pylint: disable=import-error
except ImportError:
    from urllib.parse import urlparse #pylint: disable=no-name-in-module,import-error


ATOMIC_CONFIG = util.get_atomic_config()
READ_URIS = ['file', 'http', 'https']
WRITE_URIS = ['file']

def cli(subparser):
    # atomic sign
    signer = util.get_atomic_config_item(['default_signer'])
    gnupghome = util.getgnuhome()

    signp = subparser.add_parser("sign",
                                 help="Sign an image",
                                 epilog="Create a signature for an image which can be "
                                        "used later to verify it.")
    signp.set_defaults(_class=Sign, func="sign")
    signp.add_argument("images", nargs="*", help=_("images to sign"))
    signp.add_argument("--sign-by", dest="sign_by", default=signer,
                       help=_("Name of the signing key. Currently %s, "
                              "default can be defined in /etc/atomic.conf" % signer))
    signp.add_argument("-d", "--directory",
                       default=None,
                       dest="signature_path",
                       help=_("Define an alternate directory to store signatures"))
    signp.add_argument("-g", "--gnupghome",
                       default=gnupghome,
                       dest="gnupghome",
                       help=_("Set the GNUPGHOME environment variable to "
                              "use an alternate user's GPG keyring. "
                              "Useful when running with sudo, "
                              "e.g. set to '~/.gnupg'. "
                              "Default is %s" % gnupghome
                       ))

class Sign(Atomic):
    def __init__(self): # pylint: disable=useless-super-delegation
        super(Sign, self).__init__()

    def sign(self, in_signature_path=None, images=None):
        def no_reg_no_default_error(image, registry_path):
            return "Unable to associate {} with configurations in {} and " \
                   "no 'default_store' is defined.".format(image,
                                                           registry_path)

        if in_signature_path is None and getattr(self.args, 'signature_path', None) is not None:
            in_signature_path = self.args.signature_path

        if images is None:
            images = self.args.images

        if self.args.debug:
            util.write_out(str(self.args))

        signer = self.args.sign_by

        if self.args.sign_by is None:
            raise ValueError("No default identity (default_signer) was defined in /etc/atomic.conf "
                             "and no --sign-by identity was provided.  You must provide an identity")
        registry_config_path = util.get_atomic_config_item(["registry_confdir"], ATOMIC_CONFIG, '/etc/containers/registries.d')
        registry_configs, default_store = util.get_registry_configs(registry_config_path)

        # we honor GNUPGHOME if set, override with atomic.conf, arg overrides all
        if self.args.gnupghome:
            os.environ['GNUPGHOME'] = self.args.gnupghome

        for sign_image in images:
            registry, repo, image, tag, _ = util.Decompose(sign_image).all
            ri = discovery.RegistryInspect(registry, repo, image, tag, debug=self.args.debug, orig_input=sign_image)
            manifest = ri.get_manifest(return_json=False)


            try:
                manifest_file = tempfile.NamedTemporaryFile(mode="wb", delete=False)
                manifest_file.write(manifest)
                manifest_file.close()
                manifest_hash = str(util.skopeo_manifest_digest(manifest_file.name))
                expanded_image_name = ri.fqdn
                expanded_image_name_components = util.Decompose(expanded_image_name)

                if in_signature_path:
                    if not os.path.exists(in_signature_path):
                        raise ValueError("The path {} does not exist".format(in_signature_path))
                    signature_path = in_signature_path

                else:
                    config_key = "{}/{}".format(expanded_image_name_components.registry,
                                                expanded_image_name_components.repo)
                    if not registry_configs and not default_store:
                        raise ValueError(no_reg_no_default_error(sign_image, registry_config_path))
                    reg_info = util.have_match_registry(config_key, registry_configs)
                    if not reg_info:
                        reg_info = default_store
                        if reg_info is None:
                            raise ValueError("No applicable configuration for {} was found in {}".format(config_key, registry_config_path))

                    signature_path = util.get_signature_write_path(reg_info)
                    if signature_path is None:
                        raise ValueError("No write path for {} was "
                                         "found in {}".format(config_key, registry_config_path))
                    elif urlparse(signature_path).scheme not in WRITE_URIS:
                        raise ValueError("Writing to {} is not supported. Use a supported scheme {} "
                                         "instead.".format(urlparse(signature_path).scheme, WRITE_URIS))

                    # Deal with write path prepends
                    if urlparse(signature_path).scheme in WRITE_URIS:
                        signature_path = urlparse(signature_path).path

                    # Make sure signature path exists
                    if not os.path.exists(signature_path):
                        raise ValueError("The signature path {} does not exist".format(signature_path))

                # remote_path contains neither the registry hostname nor a digest/tag
                if expanded_image_name_components.repo:
                    remote_path = expanded_image_name_components.repo + '/' + expanded_image_name_components.image
                else:
                    remote_path = expanded_image_name_components.image
                sigstore_path = "{}/{}@{}".format(signature_path, remote_path, manifest_hash.replace(':', '=', 1))

                self.make_sig_dirs(sigstore_path)
                sig_name = self.get_sig_name(sigstore_path)
                fq_sig_path = os.path.join(sigstore_path, sig_name)
                if os.path.exists(fq_sig_path):
                    raise ValueError("The signature {} already exists.  If you wish to "
                                     "overwrite it, please delete this file first")

                util.skopeo_standalone_sign(expanded_image_name, manifest_file.name,
                                            self.get_fingerprint(signer, self.args.debug), fq_sig_path, debug=self.args.debug)
                util.write_out("Created: {}".format(fq_sig_path))

            finally:
                os.remove(manifest_file.name)

    @staticmethod
    def get_fingerprint(signer, debug):
        cmd = ['gpg2', '--no-permission-warning', '--with-colons', '--fingerprint', signer]
        stderr = None if debug else util.DEVNULL
        stdout = util.check_output(cmd, stderr=stderr)
        for line in stdout.splitlines():
            _line = line.decode('utf-8')
            if _line.startswith('fpr:'):
                return _line.split(":")[9]

    @staticmethod
    def make_sig_dirs(sig_path):
        if not os.path.exists(sig_path):
            # TODO # pylint: disable=fixme
            # perhaps revisit directory permissions
            # when complete use-cases are known
            os.makedirs(sig_path)

    @staticmethod
    def get_sig_name(sig_path):
        sig_files = set(os.listdir(sig_path))
        sig_int = 1
        while True:
            name = "signature-{}".format(sig_int)
            if name not in sig_files:
                return name
            sig_int += 1
