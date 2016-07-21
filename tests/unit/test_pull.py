import unittest

from Atomic import atomic

class TestAtomicPull(unittest.TestCase):
    class Args():
        def __init__(self):
            self.image = "fedora"
            self.user = False

    def test_pull_as_privileged_user(self):
        args = self.Args()
        testobj = atomic.Atomic()
        testobj.set_args(args)
        testobj.pull_image()

    def test_pull_as_nonprivileged_user(self):
        args = self.Args()
        args.user = True
        testobj = atomic.Atomic()
        testobj.set_args(args)
        testobj.pull_image()

if __name__ == '__main__':
    unittest.main()
