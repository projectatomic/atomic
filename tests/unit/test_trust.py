import unittest
import json
import yaml
import os
import shutil

from Atomic.trust import Trust
import Atomic.util as util

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
REGISTRIESD = "etc/containers/registries.d"

class TestAtomicTrust(unittest.TestCase):

    class Args():
        def __init__(self):
            self.sigstoretype = "atomic"
            self.registry = "docker.io"
            self.pubkeys = [os.path.join(FIXTURE_DIR, "key1.pub")]
            self.sigstore = "https://sigstore.example.com/sigs"
            self.trust_type = "signedBy"
            self.keytype = "GPGKeys"
            self.assumeyes = True

    def test_sigstoretype_map_web(self):
        testobj = Trust()
        self.assertEqual(testobj.get_sigstore_type_map("web"), "docker")

    def test_sigstoretype_map_local(self):
        testobj = Trust()
        self.assertEqual(testobj.get_sigstore_type_map("local"), "dir")

    def test_setup_default_policy(self):
        args = self.Args()
        args.sigstoretype = "web"
        testobj = Trust()
        testobj.set_args(args)
        with open(os.path.join(FIXTURE_DIR, "default_policy.json"), 'r') as default:
            policy_default = json.load(default)
        policy_default = testobj.check_policy(policy_default, "docker")
        policy_expected = {"default": [{"type": "insecureAcceptAnything" }], "transports": {"docker": {}}}
        self.assertEqual(policy_default, policy_expected)

    def test_new_registry_sigstore(self):
        testobj = Trust(policy_filename = os.path.join(FIXTURE_DIR, "etc/containers/policy.json"))
        testobj.atomic_config = util.get_atomic_config(atomic_config = os.path.join(FIXTURE_DIR, "atomic.conf"))
        testobj.modify_registry_config("docker.io", "https://sigstore.example.com/sigs")
        with open(os.path.join(FIXTURE_DIR, "configs/docker.io.yaml"), 'r') as f:
            conf_expected = yaml.load(f)
        with open(os.path.join(FIXTURE_DIR, "etc/containers/registries.d/docker.io.yaml"), 'r') as f:
            conf_modified = yaml.load(f)
        self.assertEqual(conf_expected, conf_modified)

    def test_update_registry_sigstore(self):
        testobj = Trust()
        testobj.policy_filename = os.path.join(FIXTURE_DIR, "etc/containers/policy.json")
        testobj.atomic_config = util.get_atomic_config(atomic_config = os.path.join(FIXTURE_DIR, "atomic.conf"))
        testobj.modify_registry_config("docker.io", "https://sigstore.example.com/update")
        with open(os.path.join(FIXTURE_DIR, "configs/docker.io.updated.yaml"), 'r') as f:
            conf_expected = yaml.load(f)
        with open(os.path.join(FIXTURE_DIR, "etc/containers/registries.d/docker.io.yaml"), 'r') as f:
            conf_modified = yaml.load(f)
        self.assertEqual(conf_expected, conf_modified)

    def test_add_repo_sigstore(self):
        testobj = Trust(policy_filename = os.path.join(FIXTURE_DIR, "etc/containers/policy.json"))
        testobj.atomic_config = util.get_atomic_config(atomic_config = os.path.join(FIXTURE_DIR, "atomic.conf"))
        testobj.modify_registry_config("docker.io/repo", "https://sigstore.acme.com/sigs")
        with open(os.path.join(FIXTURE_DIR, "configs/docker.io-repo.yaml"), 'r') as f:
            conf_expected = yaml.load(f)
        with open(os.path.join(FIXTURE_DIR, "etc/containers/registries.d/docker.io-repo.yaml"), 'r') as f:
            conf_modified = yaml.load(f)
        self.assertEqual(conf_expected, conf_modified)

    def test_add_trust_keys(self):
        args = self.Args()
        args.sigstore = None
        testobj = Trust(policy_filename = os.path.join(FIXTURE_DIR, "etc/containers/policy.json"))
        testobj.atomic_config = util.get_atomic_config(atomic_config = os.path.join(FIXTURE_DIR, "atomic.conf"))
        testobj.set_args(args)
        testobj.add(confirm="y")
        with open(testobj.policy_filename, 'r') as f:
            d = json.load(f)
            self.assertEqual(d["transports"]["atomic"]["docker.io"][0]["keyPath"], 
                             os.path.join(FIXTURE_DIR, "key1.pub"))

    def test_modify_trust_2_keys(self):
        args = self.Args()
        args.sigstore = None
        args.pubkeys = [os.path.join(FIXTURE_DIR, "key1.pub"), os.path.join(FIXTURE_DIR, "key2.pub")]
        testobj = Trust(policy_filename = os.path.join(FIXTURE_DIR, "etc/containers/policy.json"))
        testobj.atomic_config = util.get_atomic_config(atomic_config = os.path.join(FIXTURE_DIR, "atomic.conf"))
        testobj.set_args(args)
        testobj.add(confirm="y")
        with open(testobj.policy_filename, 'r') as f:
            d = json.load(f)
            self.assertEqual(d["transports"]["atomic"]["docker.io"][1]["keyPath"], 
                             os.path.join(FIXTURE_DIR, "key2.pub"))

    def test_add_reject_type(self):
        args = self.Args()
        args.trust_type = "reject"
        args.sigstoretype = "web"
        args.pubkeys = []
        args.registry = "registry.example.com/foo"
        testobj = Trust(policy_filename = os.path.join(FIXTURE_DIR, "etc/containers/policy.json"))
        testobj.atomic_config = util.get_atomic_config(atomic_config = os.path.join(FIXTURE_DIR, "atomic.conf"))
        testobj.set_args(args)
        testobj.add()
        with open(testobj.policy_filename, 'r') as f:
            d = json.load(f)
            self.assertEqual(d["transports"]["docker"][args.registry][0]["type"], 
                             args.trust_type)

    def test_delete_trust(self):
        args = self.Args()
        args.pubkeys = []
        args.sigstoretype = "web"
        args.registry = "registry.example.com/foo"
        args.pubkeys = None
        testobj = Trust(policy_filename = os.path.join(FIXTURE_DIR, "etc/containers/policy.json"))
        testobj.atomic_config = util.get_atomic_config(atomic_config = os.path.join(FIXTURE_DIR, "atomic.conf"))
        testobj.set_args(args)
        testobj.delete()
        with open(testobj.policy_filename, 'r') as f:
            d = json.load(f)
            self.assertNotIn(args.registry, d["transports"]["docker"])


    @classmethod
    def setUpClass(cls):
        os.makedirs(os.path.join(FIXTURE_DIR, REGISTRIESD))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(os.path.join(FIXTURE_DIR, REGISTRIESD))

if __name__ == '__main__':
    unittest.main()
