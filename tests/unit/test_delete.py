#pylint: skip-file
import unittest
from Atomic.backendutils import BackendUtils
from Atomic.backends._docker import DockerBackend
from Atomic.backends._ostree import OSTreeBackend
from Atomic.syscontainers import SystemContainers
from Atomic.info import Info
from Atomic.images import Images
from Atomic.delete import Delete

no_mock = True
try:
    from unittest.mock import MagicMock, patch
    no_mock = False
except ImportError:
    try:
        from mock import MagicMock, patch
        no_mock = False
    except ImportError:
        # Mock is already set to False
        pass

docker_images = [{'Id': '7968321274dc6b6171697c33df7815310468e694ac5be0ec03ff053bb135e768', 'Size': 1109996, 'ParentId': '', 'Created': 1484345634, 'RepoTags': ['docker.io/busybox:latest'], 'VirtualSize': 1109996, 'RepoDigests': ['docker.io/busybox@sha256:817a12c32a39bbe394944ba49de563e085f1d3c5266eb8e9723256bc4448680e'], 'Labels': {}}, {'Id': '88e169ea8f46ff0d0df784b1b254a15ecfaf045aee1856dca1ec242fdd231ddd', 'Size': 3979756, 'ParentId': '', 'Created': 1482862645, 'RepoTags': ['docker.io/alpine:latest'], 'VirtualSize': 3979756, 'RepoDigests': ['docker.io/alpine@sha256:dfbd4a3a8ebca874ebd2474f044a0b33600d4523d03b0df76e5c5986cb02d7e8'], 'Labels': None}]
ostree_images = [{'Id': '5040bd2983909aa8896b9932438c3f1479d25ae837a5f6220242a264d0221f2d', 'Labels': {}, 'ImageType': 'system', 'Version': '<none>', 'ImageId': '5040bd2983909aa8896b9932438c3f1479d25ae837a5f6220242a264d0221f2d', 'RepoTags': ['<none>'], 'OSTree-rev': 'fe2619a941bff9f323d1f5eef7fc3e05f2c82d421c4ba383ec646c888231752b', 'Created': 1486143371, 'Names': []}, {'Id': 'e5599115b6a67e08278d176b05a3defb30e5564f5be6d73264ec560b484514a2', 'Labels': {}, 'ImageType': 'system', 'Version': 'debian:latest', 'ImageId': 'e5599115b6a67e08278d176b05a3defb30e5564f5be6d73264ec560b484514a2', 'RepoTags': ['debian:latest'], 'OSTree-rev': '8d4551074942f65080a613d68a21f131fdebc0bf8ce437dd676bb4dbfa50fa08', 'Created': 1486143371, 'Names': []}, {'Id': '45a2e645736c4c66ef34acce2407ded21f7a9b231199d3b92d6c9776df264729', 'Labels': {}, 'ImageType': 'system', 'Version': '<none>', 'ImageId': '45a2e645736c4c66ef34acce2407ded21f7a9b231199d3b92d6c9776df264729', 'RepoTags': ['<none>'], 'OSTree-rev': 'a2512de2d19ab0916f9acce1ebd731203a336c366a1d002126c198ceff280375', 'Created': 1486143486, 'Names': []}, {'Id': '67591570dd29de0e124ee89d50458b098dbd83b12d73e5fdaf8b4dcbd4ea50f8', 'Labels': {}, 'ImageType': 'system', 'Version': 'centos:latest', 'ImageId': '67591570dd29de0e124ee89d50458b098dbd83b12d73e5fdaf8b4dcbd4ea50f8', 'RepoTags': ['centos:latest'], 'OSTree-rev': '1ce1d5393d4c1d4e04d70576be95ca598b26dff14aa9deacc92e06df5f71c470', 'Created': 1486143486, 'Names': []}]


@unittest.skipIf(no_mock, "Mock not found")
class TestInfo(unittest.TestCase):
    class Args():
        def __init__(self):
            self.storage = None
            self.force = False
            self.all = False
            self.assumeyes = True
            self.debug = False
            self.delete_targets = []
            self.remote = False

    def test_delete_no_images(self):
        with patch('Atomic.backendutils.BackendUtils.get_images') as mockobj:
            args = self.Args()
            args.all = True
            del_ = Delete()
            del_.set_args(args)
            mockobj.return_value([])
            with self.assertRaises(ValueError):
                del_.delete_image()

    def test_delete_no_images_ostree(self):
        with patch('Atomic.backends._ostree.OSTreeBackend.get_images') as mockobj:
            args = self.Args()
            args.all = True
            args.storage = 'ostree'
            del_ = Delete()
            del_.set_args(args)
            mockobj.return_value([])
            with self.assertRaises(ValueError):
                del_.delete_image()

    def test_delete_no_images_docker(self):
        with patch('Atomic.backends._docker.DockerBackend.get_images') as mockobj:
            args = self.Args()
            args.all = True
            args.storage = 'docker'
            del_ = Delete()
            del_.set_args(args)
            mockobj.return_value([])
            with self.assertRaises(ValueError):
                del_.delete_image()

    def test_delete_all_and_images(self):
        args = self.Args()
        args.all = True
        args.delete_targets = 'foobar'
        del_ = Delete()
        del_.set_args(args)
        with self.assertRaises(ValueError):
            del_.delete_image()

    def test_delete_not_all_and_not_images(self):
        args = self.Args()
        args.delete_targets = []
        del_ = Delete()
        del_.set_args(args)
        with self.assertRaises(ValueError):
            del_.delete_image()


    def test_delete_all_docker(self):
        with patch('Atomic.backends._docker.DockerBackend.delete_image') as deleteobj:
            with patch('Atomic.backends._docker.DockerBackend._get_images') as imageobj:
                args = self.Args()
                args.all = True
                args.storage = 'docker'
                del_ = Delete()
                del_.set_args(args)
                deleteobj.return_value = None
                imageobj.return_value = docker_images
                self.assertEqual(del_.delete_image(), 0)

    def test_delete_all_ostree(self):
        with patch('Atomic.backends._ostree.OSTreeBackend.delete_image') as deleteobj:
            with patch('Atomic.syscontainers.SystemContainers.get_system_images') as imageobj:
                args = self.Args()
                args.all = True
                args.storage = 'ostree'
                del_ = Delete()
                del_.set_args(args)
                deleteobj.return_value = None
                imageobj.return_value = ostree_images
                self.assertEqual(del_.delete_image(), 0)
