import unittest
from Atomic import util
from Atomic import discovery


class TestAtomicUtil(unittest.TestCase):
    IMAGE = 'docker.io/library/busybox:latest'
    I_REGISTRY, I_REPO, I_IMAGE, I_TAG = util.decompose(IMAGE)

    def test_ping(self):
        ri = discovery.RegistryInspect(registry=self.I_REGISTRY,
                                       repo=self.I_REPO,
                                       image=self.I_IMAGE,
                                       tag=self.I_TAG)
        # No exceptions should be raised
        ri.ping()


    def test_find_image_on_registry(self):
        fq = 'docker.io/library/busybox:latest'
        for img in ['docker.io/library/busybox:latest', 'docker.io/library/busybox', 'docker.io/busybox', 'busybox']:
            registry, repo, image, tag = util.decompose(img)
            ri = discovery.RegistryInspect(registry=registry, repo=repo, image=image, tag=tag)
            self.assertEqual(ri.find_image_on_registry(), fq)

    def test_inspect(self):
        ri = discovery.RegistryInspect(registry=self.I_REGISTRY,
                                       repo=self.I_REPO,
                                       image=self.I_IMAGE,
                                       tag=self.I_TAG)
        inspect_info = ri.inspect()
        self.assertEqual(inspect_info['Name'], "{}/{}/{}".format(self.I_REGISTRY, self.I_REPO, self.I_IMAGE))
        self.assertEqual(inspect_info['Tag'], self.I_TAG)

if __name__ == '__main__':
    unittest.main()
