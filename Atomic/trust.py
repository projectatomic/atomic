from . import util
from . import Atomic
import os
import argparse
import json
import yaml

def cli(subparser):
    # atomic trust
    pubkeys_dir = util.get_atomic_config_item(['pubkeys_dir'])

    trustp = subparser.add_parser("trust",
                                  help="Manage system container trust policy",
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
                         choices=['local', 'web', 'atomic'],
                         help=sigstore_help)
    commonp.add_argument("-t", "--type", dest="trust_type", default="signedBy",
                         choices=['signedBy', 'insecureAcceptAnything', 'reject'],
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
    defaultp.set_defaults(_class=Trust, func="default")
    deletep = subparsers.add_parser("delete",
                                    help="Delete a trust policy for a registry")
    deletep.add_argument("registry",
                         help=registry_help)
    deletep.add_argument("--sigstoretype", dest="sigstoretype", default="web",
                         choices=['local', 'web', 'atomic'],
                         help=sigstore_help)
    deletep.set_defaults(_class=Trust, func="delete")

class Trust(Atomic):
    def __init__(self, policy_filename="/etc/containers/policy.json"):
        """
        :param policy_filename: override policy filename
        """
        super(Trust, self).__init__()
        self.policy_filename = policy_filename
        self.atomic_config = util.get_atomic_config()

    def add(self):
        """
        Add or prompt to modify policy.json file and registries.d registry configuration
        """
        sstype = self.get_sigstore_type_map(self.args.sigstoretype)
        with open(self.policy_filename, 'r+') as policy_file:
            policy = json.load(policy_file)
            policy = self.check_policy(policy)
            if self.args.registry in policy["transports"][sstype]:
                confirm = None
                if self.args.assumeyes:
                    confirm = "yes"
                else:
                    confirm = util.input("Trust policy already defined for %s:%s\nDo you want to overwrite? (y/N) " % (self.args.sigstoretype, self.args.registry))
                if not "y" in confirm.lower():
                    exit(0)
            payload = []
            for k in self.args.pubkeys:
                if not os.path.exists(k):
                    raise ValueError("The public key file %s was not found. This file must exist to proceed." % k)
                payload.append({ "type": self.args.trust_type, "keyType": self.args.keytype, "keyPath": k })
            if self.args.trust_type == "signedBy":
                if len(self.args.pubkeys) == 0:
                    raise ValueError("At least one public key must be defined for type 'signedBy'")
            else:
                payload.append({ "type": self.args.trust_type })
            policy["transports"][sstype][self.args.registry] = payload
            policy_file.seek(0)
            json.dump(policy, policy_file, indent=4)
            policy_file.truncate()
            if self.args.sigstore:
                if sstype == "atomic":
                    raise ValueError("Sigstore cannot be defined for sigstoretype 'atomic'")
                else:
                    self.modify_registry_config(self.args.registry, self.args.sigstore)

    def delete(self):
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

    def default(self):
        with open(self.policy_filename, 'r+') as policy_file:
            policy = json.load(policy_file)
            default_type_map = { "accept": "insecureAcceptAnything", "reject": "reject" }
            policy["default"][0]["type"] = default_type_map[self.args.default_policy]
            policy_file.seek(0)
            json.dump(policy, policy_file, indent=4)
            policy_file.truncate()

    def check_policy(self, policy):
        """
        Prep the policy file with required data structure
        :param policy: policy data
        :return: modified policy
        """
        sstype = self.get_sigstore_type_map(self.args.sigstoretype)
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
        if (not reg_info or registry not in registry_configs):
            # no existing configuration found for this registry
            if not os.path.exists(reg_yaml_file):
                with open(reg_yaml_file, 'w') as reg_file:
                    d = { "docker": { registry: { "sigstore": sigstore }}}
                    yaml.dump(d, reg_file, default_flow_style=False)
            elif os.path.exists(reg_yaml_file):
                # The filename we expect to use already exists
                # Open an existing file and add a new key for this registry
                self.write_registry_config_file(reg_yaml_file, registry, sigstore)
        else:
            if not sigstore == registry_configs[registry]["sigstore"]:
                # We're modifying an existing configuration
                # use the same filename
                self.write_registry_config_file(registry_configs[registry]["filename"],
                                                registry,
                                                sigstore)

    def write_registry_config_file(self, reg_file, registry, sigstore):
        """
        Utility method to modify existing registry config file
        :param reg_file: registry filename
        :param registry: registry name
        :param sigstore: sigstore server
        """
        with open(reg_file, 'r+') as f:
            d = yaml.load(f)
            d["docker"][registry] = { "sigstore": sigstore }
            f.seek(0)
            yaml.dump(d, f, default_flow_style=False)
            f.truncate()

    def get_sigstore_type_map(self, sigstore_type):
        """
        Get the skopeo trust policy type for user-friendly value
        :param sigstore_type: one of web,local,atomic
        :return: skopeo trust policy type string
        """
        t = { "web": "docker", "local": "dir", "atomic": "atomic" }
        return t[sigstore_type]
