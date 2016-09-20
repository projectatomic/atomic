from . import util
from . import Atomic
import os
import argparse
import json
import yaml
import requests
import collections

TRANSPORT_TYPES = ["docker", "atomic", "web"]

def cli(subparser):
    # atomic trust
    pubkeys_dir = util.get_atomic_config_item(['pubkeys_dir'])

    trustp = subparser.add_parser("trust",
                                  help=_("Manage system container trust policy"),
                                  epilog="Manages the trust policy of the host system. "
                                         "Trust policy describes a registry scope "
                                         "that must be signed by public keys.")
    commonp = argparse.ArgumentParser(add_help=False)
    registry_help="""Registry to manage trust policy for, REGISTRY[/REPOSITORY].
                     Trust policy allows for nested scope.
                     Example: registry.example.com defines trust for entire registry.
                     Example: registry.example.com/acme defines trust for specific repository."""
    sigstore_help="""Signature server type (default: web)
                     local: local file 
                     web: remote web server 
                     atomic: openshift-based atomic registry"""
    commonp.add_argument("-k", "--pubkeys", nargs='?', default=[],
                         action="append", dest="pubkeys",
                         help=_("Absolute path of installed public key(s) to trust for TARGET. "
                                "May used multiple times to define multiple public keys. "
                                "File(s) must exist before using this command. "
                                "Default directory is %s" % pubkeys_dir))
    commonp.add_argument("--sigstoretype", dest="sigstoretype", default="web",
                         choices=['atomic', 'local', 'web'],
                         help=sigstore_help)
    commonp.add_argument("-t", "--type", dest="trust_type", default="signedBy",
                         choices=['insecureAcceptAnything', 'reject', 'signedBy'],
                         help="Trust type (default: signedBy)")
    commonp.add_argument("--keytype", dest="keytype", default="GPGKeys",
                         help="Public key type (default: GPGKeys)")
    commonp.add_argument("-s", "--sigstore", dest="sigstore",
                         help=_("URL and path of remote signature server, "
                                "https://sigstore.example.com/signatures. "
                                "Ignored with 'atomic' sigstoretype."))
    commonp.add_argument("registry", 
                         help=registry_help)
    subparsers = trustp.add_subparsers()
    addp = subparsers.add_parser("add", parents=[commonp],
                                 help="Add a new trust policy for a registry")
    addp.set_defaults(_class=Trust, func="add")
    defaultp = subparsers.add_parser("default",
                                 help="Modify default trust policy")
    defaultp.add_argument("default_policy", choices=["reject", "accept"],
                                 help="Default policy action")
    defaultp.set_defaults(_class=Trust, func="modify_default")
    deletep = subparsers.add_parser("delete",
                                    help="Delete a trust policy for a registry")
    deletep.add_argument("registry",
                         help=registry_help)
    deletep.add_argument("--sigstoretype", dest="sigstoretype", default="web",
                         choices=['atomic', 'local', 'web'],
                         help=sigstore_help)
    deletep.set_defaults(_class=Trust, func="delete")
    showp = subparsers.add_parser("show",
                                  help="Display trust policy for the system")
    showp.add_argument('-j', '--json', action='store_true', help="Output policy file as raw json")
    showp.set_defaults(_class=Trust, func="show")

class Trust(Atomic):
    def __init__(self, policy_filename="/etc/containers/policy.json"):
        """
        :param policy_filename: override policy filename
        """
        super(Trust, self).__init__()
        self.policy_filename = policy_filename
        self.atomic_config = util.get_atomic_config()

    def add(self, registry=None, pubkeys=None, sigstore=None, sigstoretype=None, keytype=None, trust_type=None):
        """
        Add trust to policy.json file and optionally update registries.d registry configuration
        :param sigstoretype: string, human-readable sigstore type, one of "atomic", "web", "local"
        :param registry: the registry[/repo] to add policy for
        :param pubkeys: list of pubkeys to add with trust_type "signedBy"
        :param keytype: string, "GPGKeys"
        :param trust_type: string, one of "signedBy", "insecureAcceptAnything", "reject"
        :param sigstore: string, URL of signature server
        """
        if registry is None:
            registry=self.args.registry
        if pubkeys is None:
            pubkeys=self.args.pubkeys
        if sigstoretype is None:
            sigstoretype=self.args.sigstoretype
        if keytype is None:
            keytype=self.args.keytype
        if trust_type is None:
            trust_type=self.args.trust_type
        if sigstore is None:
            sigstore=self.args.sigstore
        sstype = self.get_sigstore_type_map(sigstoretype)

        mode = "r+" if os.path.exists(self.policy_filename) else "w+"
        with open(self.policy_filename, mode) as policy_file:
            if mode == "r+":
                policy = json.load(policy_file)
                policy = self.check_policy(policy, sstype)
                if registry in policy["transports"][sstype]:
                    if not self.args.assumeyes:
                        confirm = util.input("Trust policy already defined for %s:%s\nDo you want to overwrite? (y/N) " % (sigstoretype, registry))
                        if not "y" in confirm.lower():
                            exit(0)
            else:
                policy={"transports":{sstype:{}}}

            payload = []
            for k in pubkeys:
                if not os.path.exists(k):
                    raise ValueError("The public key file %s was not found. This file must exist to proceed." % k)
                payload.append({ "type": trust_type, "keyType": keytype, "keyPath": k })
            if trust_type == "signedBy":
                if len(pubkeys) == 0:
                    raise ValueError("At least one public key must be defined for type 'signedBy'")
            else:
                payload.append({ "type": trust_type })
            policy["transports"][sstype][registry] = payload
            policy_file.seek(0)
            json.dump(policy, policy_file, indent=4)
            policy_file.truncate()
            if sigstore:
                if sstype == "atomic":
                    raise ValueError("Sigstore cannot be defined for sigstoretype 'atomic'")
                else:
                    self.modify_registry_config(registry, sigstore)

    def delete(self):
        """
        Remove trust policy entry
        """
        sstype = self.get_sigstore_type_map(self.args.sigstoretype)
        with open(self.policy_filename, 'r+') as policy_file:
            policy = json.load(policy_file)
            try:
                del policy["transports"][sstype][self.args.registry]
            except KeyError:
                raise ValueError("Could not find trust policy defined for %s transport %s" % 
                              (self.args.sigstoretype, self.args.registry))
            policy_file.seek(0)
            json.dump(policy, policy_file, indent=4)
            policy_file.truncate()

    def modify_default(self):
        """
        Modify global trust policy default
        """
        mode = "r+" if os.path.exists(self.policy_filename) else "w+"
        with open(self.policy_filename, mode) as policy_file:
            if mode == "r+":
                policy = json.load(policy_file)
            else:
                policy = {}

            default_type_map = { "accept": "insecureAcceptAnything", "reject": "reject" }
            if "default" in policy:
                policy["default"][0]["type"] = default_type_map[self.args.default_policy]
            else:
                policy["default"] = [ { "type": default_type_map[self.args.default_policy] }]

            policy_file.seek(0)
            json.dump(policy, policy_file, indent=4)
            policy_file.truncate()

    def install_pubkey(self, key_name, key_url):
        """
        Installs remote public key to system config directory
        :param key_name: id of key used as filename
        :param key_url: download URI of public key
        :return: pubkey path string or False
        """
        pubkeys_dir = util.get_atomic_config_item(['pubkeys_dir'], util.get_atomic_config())
        pubkey_file = "%s/%s" % (pubkeys_dir, key_name)
        if not os.path.exists(pubkeys_dir):
            os.mkdir(pubkeys_dir)
        if os.path.exists(pubkey_file):
            util.write_out("Public key %s already installed at %s" % (key_name, pubkey_file))
        else:
            r = requests.get(key_url)
            if r.status_code == 200:
                with open(pubkey_file, 'w') as pubfile:
                    pubfile.write(r.content)
                util.write_out("Installed public key %s" % pubkey_file)
            else:
                util.write_out("WARNING: Could not download public key using URL %s." % key_url)
                util.write_out("Download the public key manually and install as %s" % pubkey_file)
        return pubkey_file

    def check_policy(self, policy, sstype):
        """
        Prep the policy file with required data structure
        :param policy: policy data
        :param sstype: sigstore type
        :return: modified policy
        """
        if not "transports" in policy:
            policy["transports"] = {}
        if not sstype in policy["transports"]:
            policy["transports"][sstype] = {}
        return policy

    def modify_registry_config(self, registry, sigstore):
        """
        Modify the registries.d configuration for a registry
        :param registry: a registry name
        :param sigstore: a file:/// or https:// URL
        """
        registry_config_path = util.get_atomic_config_item(["registry_confdir"], self.atomic_config)
        registry_configs, _ = util.get_registry_configs(registry_config_path)
        reg_info = util.have_match_registry(registry, registry_configs)
        reg_yaml_file = "%s.yaml" % os.path.join(registry_config_path, registry.replace("/", "-"))
        mode = "r+"
        if (not reg_info or registry not in registry_configs):
            if not os.path.exists(reg_yaml_file):
                mode="w+"
        else:
            if not sigstore == registry_configs[registry]["sigstore"]:
                reg_yaml_file = registry_configs[registry]["filename"]
        self.write_registry_config_file(reg_yaml_file, registry, sigstore, mode=mode)

    def write_registry_config_file(self, reg_file, registry, sigstore, mode="r+"):
        """
        Utility method to modify existing registry config file
        :param reg_file: registry filename
        :param registry: registry name
        :param sigstore: sigstore server
        :param mode: file open mode
        """
        with open(reg_file, mode) as f:
            d = yaml.load(f)
            d = { "docker": {}}
            d["docker"][str(registry)] = { "sigstore": str(sigstore) }
            f.seek(0)
            yaml.dump(d, f, default_flow_style=False)
            f.truncate()

    def get_sigstore_type_map(self, sigstore_type):
        """
        Given the user-friendly trust type, get the skopeo value
        :param sigstore_type: one of web,local,atomic
        :return: skopeo trust policy type string
        """
        t = { "docker": "docker", "web": "docker", "local": "dir", "dir": "dir", "atomic": "atomic" }
        if sigstore_type not in t:
            raise ValueError("Invalid sigstore type %s" % sigstore_type)
        return t[sigstore_type]

    def discover_sigstore(self, pull_image):
        """
        Check for registry/repo/sigstore metadata image
        prompt user for trust on first use workflow
        :param pull_image: image being pulled, used to discover matching sigstore meta image
        """
        if not util.get_atomic_config_item(['discover_sigstores'], util.get_atomic_config()):
            return True
        (registry, repo, _) = util.decompose(pull_image)
        repo = repo.split('/')
        registry_config_path = util.get_atomic_config_item(["registry_confdir"], self.atomic_config)
        registry_configs, _ = util.get_registry_configs(registry_config_path)
        sigstore_labels = False
        scope = '/'.join([registry, repo[0]])
        if not scope in registry_configs:
            sigstore_labels = self.get_sigstore_image_metadata(registry, repo[0])
            if not sigstore_labels:
                scope = registry
                if not scope in registry_configs:
                    sigstore_labels = self.get_sigstore_image_metadata(registry)
        if self._validate_sigstore_labels(sigstore_labels):
            if self.prompt_trust(sigstore_labels):
                pubkey_path = self.install_pubkey(sigstore_labels['pubkey-id'], sigstore_labels['pubkey-url'])
                explicit_sigstoretype = "web"
                if sigstore_labels['sigstore-type']:
                    explicit_sigstoretype = sigstore_labels['sigstore-type']
                self.add(registry=scope, trust_type="signedBy", sigstoretype=explicit_sigstoretype, keytype="GPGKeys", pubkeys=[pubkey_path], sigstore=sigstore_labels['sigstore-url'])

    def get_sigstore_image_metadata(self, registry, repo=None):
        """
        Get sigstore metadata image
        :param registry: registry string
        :param repo: repo string
        :return dict of labels or False
        """
        _img = util.get_atomic_config_item(['sigstore_metadata_image'], util.get_atomic_config())
        if repo:
            sigstoreimage = '/'.join([registry, repo, _img])
        else:
            sigstoreimage = '/'.join([registry, _img])
        try:
            data = util.skopeo_inspect("docker://" + sigstoreimage, args=None)
        except ValueError:
            data = None
        if data:
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
        is_valid = False
        if labels:
            # sigstore-type is optional
            expected_keys = ["pubkey-id", "pubkey-fingerprint", "pubkey-url", "sigstore-url"]
            for k in expected_keys:
                is_valid = k in labels
        return is_valid

    def prompt_trust(self, labels):
        """
        Prompt user for trust on first use workflow
        :param labels: dict of metadata labels defining sigstore trust
        :return: True if user accepts
        """
        util.write_out("ID: " + labels['pubkey-id'])
        util.write_out("Fingerprint: " + labels['pubkey-fingerprint'])
        util.write_out("Public key download URL: %s" % labels['pubkey-url'])
        if not self.args.assumeyes:
            confirm = util.input("Do you want to add trust policy for this registry? (y/N) ")
            if not "y" in confirm.lower():
                return False
        return True

    def show(self):
        """
        Display trust policy
        If policy.json doesn't exist, create it, then display
        """
        registry_config_path = util.get_atomic_config_item(["registry_confdir"], self.atomic_config)
        registry_configs, _ = util.get_registry_configs(registry_config_path)
        policy = None
        mode = "r+" if os.path.exists(self.policy_filename) else "w+"
        with open(self.policy_filename, mode) as policy_file:
            if mode == "r+":
                policy = json.load(policy_file)
            else:
                policy={ "default": [{ "type": "insecureAcceptAnything" }] }
                policy_file.seek(0)
                json.dump(policy, policy_file, indent=4)
                policy_file.truncate()
            if self.args.json:
                util.output_json(policy)
            else:
                table = {}
                if "transports" in policy:
                    for tt in TRANSPORT_TYPES:
                        if tt in policy["transports"]:
                            for key, value in policy["transports"][tt].items():
                                table[key] = { "type": value[0]["type"] }
                                reg_info = util.have_match_registry(key, registry_configs)
                                if reg_info:
                                    table[key]["sigstore"] = reg_info["sigstore"]
                                else:
                                    table[key]["sigstore"] = ""

                sorted_table = collections.OrderedDict(sorted(table.items()))
                for key, value in sorted_table.items():
                    util.write_out('{0:<35} {1:<8} {2}'.format(key, self.trusttype_map(value["type"]), value["sigstore"]))
                util.write_out('{0:<35} {1:<8}'.format("* (default)", self.trusttype_map(policy["default"][0]["type"])))

    def trusttype_map(self, trust_type):
        t = { "insecureAcceptAnything": "accept", "signedBy": "signed", "reject": "reject" }
        if trust_type not in t:
            raise ValueError("Invalid trust type %s" % trust_type)
        return t[trust_type]
