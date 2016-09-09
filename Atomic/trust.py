from . import util
from . import Atomic
import os
import argparse
import json
from .atomic import AtomicError


ATOMIC_CONFIG = util.get_atomic_config()
POLICY_FILE = "/etc/containers/policy.json"

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
    sigstore_help="""Signature server type (default: atomic)
                     dir: local file 
                     docker: static web server 
                     atomic: openshift-based atomic registry"""
    commonp.add_argument("--pubkeys", dest="pubkeys", nargs='*',
                         help=_("Absolute path of installed public key(s) to trust for TARGET. "
                                "May be a list of multiple trusted public keys. "
                                "File(s) must exist before using this command. "
                                "Default directory is %s" % pubkeys_dir))
    commonp.add_argument("--sigstoretype", dest="sigstoretype", default="atomic",
                         choices=['dir', 'docker', 'atomic'],
                         help=sigstore_help)
    commonp.add_argument("--type", dest="trust_type", default="signedBy",
                         choices=['signedBy', 'insecureAcceptAnything', 'reject'],
                         help="Trust type (default: signedBy)")
    commonp.add_argument("--keytype", dest="keytype", default="GPGKeys",
                         help="Public key type (default: GPGKeys)")
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
    removep.add_argument("--sigstoretype", dest="sigstoretype", default="atomic",
                         choices=['dir', 'docker', 'atomic'],
                         help=sigstore_help)
    removep.set_defaults(_class=Trust, func="remove")

class Trust(Atomic):

    def add(self):
        with open(POLICY_FILE, 'r+') as policy_file:
            policy = json.load(policy_file)
            policy = self.check_policy(policy)
            if self.args.registry in policy["transports"][self.args.sigstoretype]:
                overwrite = util.input("Trust policy already defined for %s:%s\nDo you want to overwrite? (y/N) " % 
                                      (self.args.sigstoretype, self.args.registry))
                if not "y" in overwrite.lower():
                    util.write_out("Trust policy not updated")
                    exit(0)
            payload = []
            if self.args.pubkeys:
                for k in self.args.pubkeys:
                    if not os.path.exists(k):
                        raise ValueError("The public key file %s was not found. This file must exist to proceed." % k)
                    payload.append({ "type": self.args.trust_type, "keyType": self.args.keytype, "keyPath": k })
            elif self.args.trust_type:
                payload.append({ "type": self.args.trust_type })
            policy["transports"][self.args.sigstoretype][self.args.registry] = payload
            policy_file.seek(0)
            json.dump(policy, policy_file, indent=4)
            print("Added trust policy for %s transport %s" % (self.args.sigstoretype, self.args.registry))

    def remove(self):
        with open(POLICY_FILE, 'r+') as policy_file:
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
        if not os.path.exists(POLICY_FILE):
            raise ValueError("The policy file %s was not found. This file must exist to proceed." % POLICY_FILE)
        if not "transports" in policy:
            policy["transports"] = {}
        if not self.args.sigstoretype in policy["transports"]:
            policy["transports"][self.args.sigstoretype] = {}
        return policy

