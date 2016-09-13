import unittest
import json

from Atomic.trust import Trust

class TestAtomicTrust(unittest.TestCase):
    class Args():
        def __init__(self):
            self.sigstoretype = "docker"

    def test_check_policy(self):
        args = self.Args()
        testobj = Trust()
        testobj.set_args(args)
        with open("fixtures/default_policy.json", 'r') as default:
            policy_default = json.load(default)
        policy_default = testobj.check_policy(policy_default)
        policy_expected = {"default": [{"type": "insecureAcceptAnything" }], "transports": {"docker": {}}}
        self.assertEqual(policy_default, policy_expected)

 
if __name__ == '__main__':
    unittest.main()
