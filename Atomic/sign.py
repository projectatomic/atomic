from . import util
from . import Atomic
import os
import tempfile
from .atomic import AtomicError
import re


ATOMIC_CONFIG = util.get_atomic_config()

def cli(subparser):
    # atomic sign
    signer = ATOMIC_CONFIG.get('default_signer', None)
    signature_path = util.get_atomic_config_item(['default-sigstore-path'], atomic_config=ATOMIC_CONFIG)
    if signature_path is None:
        signature_path = util.ATOMIC_VAR_LIB + '/sigstore'

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
                       default=signature_path,
                       dest="signature_path",
                       help=_("The directory to store signatures under: Default {}.".format(signature_path) ))

class Sign(Atomic):
    def sign(self):
        # TODO
        # Atomic is run as sudo. Should we work around that?

        if self.args.debug:
            util.write_out(str(self.args))

        signer = self.args.sign_by

        for sign_image in self.args.images:
            remote_inspect_info = util.skopeo_inspect("docker://{}".format(sign_image))
            manifest = util.skopeo_inspect('docker://{}'.format(sign_image), args=['--raw'], return_json=False)
            try:
                manifest_file = tempfile.NamedTemporaryFile(mode="wb", delete=False)
                manifest_file.write(manifest)
                manifest_file.close()
                manifest_hash = str(util.skopeo_manifest_digest(manifest_file.name))

                expanded_image_name = str(remote_inspect_info['Name'])
                sigstore_path = "{}/{}/{}@{}".format(self.args.signature_path, os.path.dirname(expanded_image_name),
                                                     os.path.basename(expanded_image_name), manifest_hash)
                self.make_sig_dirs(sigstore_path)
                sig_name = self.get_sig_name(sigstore_path)
                fq_sig_path = os.path.join(sigstore_path, sig_name)
                if os.path.exists(fq_sig_path):
                    raise ValueError("The signature {} already exists.  If you wish to "
                                     "overwrite it, please delete this file first")

                util.skopeo_standalone_sign(expanded_image_name, manifest_file.name,
                                            self.get_fingerprint(signer), fq_sig_path)
                util.write_out("Created: {}".format(fq_sig_path))

            finally:
                os.remove(manifest_file.name)

    def check_input_validity(self):
        try:
            for image in self.args.images:
                self._is_image(image)
        except AtomicError:
            raise ValueError("{} is not a valid image".format(image))

    @staticmethod
    def get_fingerprint(signer):
        cmd = ['gpg', '--no-permission-warning', '--with-colons', '--fingerprint', signer]
        return_code, stdout, stderr = util.subp(cmd, newline=True)
        if return_code is not 0:
            raise ValueError(stderr)
        for line in stdout.splitlines():
            if line.startswith('fpr:'):
                return line.split(":")[9]

    @staticmethod
    def make_sig_dirs(sig_path):
        if not os.path.exists(sig_path):
            # TODO
            # perhaps revisit directory permissions
            # when complete use-cases are known
            os.makedirs(sig_path, '0777')

    @staticmethod
    def get_sig_name2(sig_path):
        def missing_ints(aoi):
            # Returns a list of integers in range
            start, end = 1, max(aoi) + 1
            if start == end and start is not 1:
                start = 1
            _diff = sorted(set(range(start, end)).difference(aoi))
            if len(_diff) == 0:
                return end
            else:
                return min(_diff)

        sigs = []
        for sig in os.listdir(sig_path):
            if re.match(r"signature-\b[0-9]+\b(?!\.[0-9])", sig):
                sigs.append(int(sig.replace("signature-", "")))

        sigs.sort()
        if len(sigs) == 0:
            return "signature-1"
        # In the event signature-0 exists
        if sigs[0] == 0:
            del sigs[0]
        missing = missing_ints(sigs)
        if missing == 0:
            sig_int = max(sigs) + 1
        else:
            sig_int = missing
        return "signature-{}".format(sig_int)

    @staticmethod
    def get_sig_name(sig_path):
        sig_files = set(os.listdir(sig_path))
        sig_int = 1
        while True:
            name = "signature-{}".format(sig_int)
            if name not in sig_files:
                return name
            sig_int += 1
