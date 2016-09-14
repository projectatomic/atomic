from . import util
from . import Atomic
import os
import argparse
import json
import yaml

ATOMIC_CONFIG = util.get_atomic_config()

def cli(subparser):
    # atomic trust
    pubkeys_dir = util.get_atomic_config_item(['pubkeys_dir'], atomic_config=ATOMIC_CONFIG)

    trustp = subparser.add_parser("trust",
                                 description="Manage trust policy for registries")
    commonp = argparse.ArgumentParser(add_help=False)
    registry_help="""Registry to manage trust policy for, REGISTRY[/REPOSITORY].
                          Trust policy allows for nested scope.
                          Example: registry.example.com defines trust for entire registry.
                          Example: registry.example.com/acme defines trust for specific repository."""
    sigstore_help="""Signature server type (default: docker)
                     dir: local file 
                     docker: static web server 
                     atomic: openshift-based atomic registry"""
    commonp.add_argument("--pubkeys", dest="pubkeys", nargs='*',
                         help=_("Absolute path of installed public key(s) to trust for TARGET. "
                                "May be a list of multiple trusted public keys. "
                                "File(s) must exist before using this command. "
                                "Default directory is %s" % pubkeys_dir))
    commonp.add_argument("--sigstoretype", dest="sigstoretype", default="docker",
                         choices=['dir', 'docker', 'atomic'],
                         help=sigstore_help)
    commonp.add_argument("--type", dest="trust_type", default="signedBy",
                         choices=['signedBy', 'insecureAcceptAnything', 'reject'],
                         help="Trust type (default: signedBy)")
    commonp.add_argument("--keytype", dest="keytype", default="GPGKeys",
                         help="Public key type (default: GPGKeys)")
    commonp.add_argument("--sigstore", dest="sigstore",
                         help=_("URL and path of remote signature server, "
                                "https://sigstore.example.com/signatures. "
                                "Ignored with 'atomic' sigstoretype."))
    commonp.add_argument("registry", 
                         help=registry_help)
    subparsers = trustp.add_subparsers()
    addp = subparsers.add_parser("add", parents=[commonp],
                                 help="Add a new trust policy for a registry")
    addp.set_defaults(_class=Trust, func="add")
    removep = subparsers.add_parser("remove",
                                    help="Remove a trust policy for a registry")
    removep.add_argument("registry", 
                         help=registry_help)
    removep.add_argument("--sigstoretype", dest="sigstoretype", default="docker",
                         choices=['dir', 'docker', 'atomic'],
                         help=sigstore_help)
    removep.set_defaults(_class=Trust, func="remove")

class Trust(Atomic):
    def __init__(self):
        super(Trust, self).__init__()
        self.policy_filename = "/etc/containers/policy.json"
        self.atomic_config = util.get_atomic_config()

    def add(self):
        """
        Add or prompt to modify policy.json file and registries.d registry configuration
        """
        with open(self.policy_filename, 'r+') as policy_file:
            policy = json.load(policy_file)
            policy = self.check_policy(policy)
            if self.args.registry in policy["transports"][self.args.sigstoretype]:
                confirm = None
                if self.args.assumeyes:
                    confirm = "yes"
                else:
                    confirm = util.input("Trust policy already defined for %s:%s\nDo you want to overwrite? (y/N) " % (self.args.sigstoretype, self.args.registry))
                if not "y" in confirm.lower():
                    util.write_out("Trust policy not modified")
                    exit(0)
            payload = []
            if self.args.pubkeys:
                keys = self.args.pubkeys.split(" ")
                for k in keys:
                    if not os.path.exists(k):
                        raise ValueError("The public key file %s was not found. This file must exist to proceed." % k)
                    payload.append({ "type": self.args.trust_type, "keyType": self.args.keytype, "keyPath": k })
            elif self.args.trust_type:
                if (self.args.trust_type == "signedBy" and not self.args.pubkeys):
                    raise ValueError("At least one public key must be defined for type 'signedBy'")
                else:
                    payload.append({ "type": self.args.trust_type })
            policy["transports"][self.args.sigstoretype][self.args.registry] = payload
            policy_file.seek(0)
            json.dump(policy, policy_file, indent=4)
            policy_file.truncate()
            if self.args.sigstore:
                if self.args.sigstoretype == "atomic":
                    util.write_out("Sigstore cannot be defined for sigstoretype 'atomic'")
                else:
                    self.modify_registry_config(self.args.registry, self.args.sigstore)
            util.write_out("Added trust policy for %s transport %s" % (self.args.sigstoretype, self.args.registry))

    def remove(self):
        with open(self.policy_filename, 'r+') as policy_file:
            policy = json.load(policy_file)
            try:
                del policy["transports"][self.args.sigstoretype][self.args.registry]
            except KeyError:
                util.write_out("Could not find trust policy defined for %s transport %s" % 
                              (self.args.sigstoretype, self.args.registry))
                exit(1)
            policy_file.seek(0)
            json.dump(policy, policy_file, indent=4)
            policy_file.truncate()
            util.write_out("Removed trust policy for %s:%s" % (self.args.sigstoretype, self.args.registry))

    def check_policy(self, policy):
        """
        Prep the policy file with required data structure
        :param policy: policy data
        :return: modified policy
        """
        if not "transports" in policy:
            policy["transports"] = {}
        if not self.args.sigstoretype in policy["transports"]:
            policy["transports"][self.args.sigstoretype] = {}
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
                    util.write_out("Added registry config file %s" % reg_yaml_file)
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
            else:
                util.write_out("No change to registry sigstore")

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
            util.write_out("Updated registry config file %s" % reg_file)

