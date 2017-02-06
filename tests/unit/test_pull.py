#pylint: skip-file
import unittest
from Atomic.pull import Pull
from Atomic.syscontainers import SystemContainers
from Atomic.backends._docker import DockerBackend
from Atomic import util

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

class TestAtomicPull(unittest.TestCase):
    class Args():
        def __init__(self):
            self.image = "docker:centos"
            self.user = False

    def test_pull_as_privileged_user(self):
        args = self.Args()
        testobj = SystemContainers()
        testobj.set_args(args)
        testobj.pull_image()

    def test_pull_as_nonprivileged_user(self):
        args = self.Args()
        args.user = True
        testobj = SystemContainers()
        testobj.set_args(args)
        testobj.pull_image()

remote_inspect_info = {'Layers': ['sha256:56bec22e355981d8ba0878c6c2f23b21f422f30ab0aba188b54f1ffeff59c190'], 'Labels': {}, 'Created': '2016-10-07T21:03:58.469866982Z', 'Tag': '', 'Name': 'docker.io/library/busybox', 'Os': 'linux', 'id': 'sha256:e02e811dd08fd49e7f6032625495118e63f597eb150403d02e3238af1df240ba', 'Architecture': 'amd64', 'Digest': 'sha256:29f5d56d12684887bdfa50dcd29fc31eea4aaf4ad3bec43daf19026a7ce69912', 'RepoTags': ['1-glibc', '1-musl', '1-ubuntu', '1-uclibc', '1.21-ubuntu', '1.21.0-ubuntu', '1.23.2', '1.23', '1.24-glibc', '1.24-musl', '1.24-uclibc', '1.24.0', '1.24.1-glibc', '1.24.1-musl', '1.24.1-uclibc', '1.24.1', '1.24.2-glibc', '1.24.2-musl', '1.24.2-uclibc', '1.24.2', '1.24', '1.25-glibc', '1.25-musl', '1.25-uclibc', '1.25.0-glibc', '1.25.0-musl', '1.25.0-uclibc', '1.25.0', '1.25.1-glibc', '1.25.1-musl', '1.25.1-uclibc', '1.25.1', '1.25', '1.26-glibc', '1.26-musl', '1.26-uclibc', '1.26.0-glibc', '1.26.0-musl', '1.26.0-uclibc', '1.26.0', '1.26.1-glibc', '1.26.1-musl', '1.26.1-uclibc', '1.26.1', '1.26.2-glibc', '1.26.2-musl', '1.26.2-uclibc', '1.26.2', '1.26', '1', 'buildroot-2013.08.1', 'buildroot-2014.02', 'glibc', 'latest', 'musl', 'ubuntu-12.04', 'ubuntu-14.04', 'ubuntu', 'uclibc'], 'DockerVersion': '1.12.1'}
local_inspect_info = {'RepoDigests': ['docker.io/busybox@sha256:29f5d56d12684887bdfa50dcd29fc31eea4aaf4ad3bec43daf19026a7ce69912'], 'ContainerConfig': {'StdinOnce': False, 'Cmd': ['/bin/sh', '-c', '#(nop) ', 'CMD ["sh"]'], 'OnBuild': None, 'Env': ['PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'], 'AttachStdout': False, 'User': '', 'Labels': {}, 'Image': '1679bae2167496818312013654f5c66a16e185d0a0f6b762b53c8558014457c6', 'OpenStdin': False, 'AttachStderr': False, 'AttachStdin': False, 'Domainname': '', 'Entrypoint': None, 'Hostname': '4a74292706a0', 'Volumes': None, 'WorkingDir': '', 'Tty': False}, 'DockerVersion': '1.12.1', 'RepoTags': [], 'RootFS': {'Type': 'layers', 'Layers': ['e88b3f82283bc59d5e0df427c824e9f95557e661fcb0ea15fb0fb6f97760f9d9']}, 'Created': '2016-10-07T21:03:58.469866982Z', 'Architecture': 'amd64', 'Id': 'e02e811dd08fd49e7f6032625495118e63f597eb150403d02e3238af1df240ba', 'GraphDriver': {'Data': {'DeviceName': 'docker-253:2-5900125-83ca47b12d877ce22ea1c633d2425fb245902a5db0a0039f010d0a7d4ee10b91', 'DeviceId': '2611', 'DeviceSize': '10737418240'}, 'Name': 'devicemapper'}, 'Size': 1093484, 'Config': {'StdinOnce': False, 'Cmd': ['sh'], 'OnBuild': None, 'Env': ['PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'], 'AttachStdout': False, 'User': '', 'Labels': {}, 'Image': '1679bae2167496818312013654f5c66a16e185d0a0f6b762b53c8558014457c6', 'OpenStdin': False, 'AttachStderr': False, 'AttachStdin': False, 'Domainname': '', 'Entrypoint': None, 'Hostname': '4a74292706a0', 'Volumes': None, 'WorkingDir': '', 'Tty': False}, 'Comment': '', 'Os': 'linux', 'Author': '', 'Container': '8bb318a3b4672c53a1747991c95fff3306eea13ec308740ebe0c81b56ece530f', 'Parent': '', 'VirtualSize': 1093484}

@unittest.skipIf(no_mock, "Mock not found")
class TestAtomicPullByDigest(unittest.TestCase):
    class Args():
        def __init__(self):
            self.debug = None
            self.assumeyes = None

    def test_pull_by_digest(self):
        image_name = "docker.io/busybox@sha256:29f5d56d12684887bdfa50dcd29fc31eea4aaf4ad3bec43daf19026a7ce69912"
        db = DockerBackend()
        img_obj = db._make_remote_image(image_name)
        img_obj.remote_inspect = MagicMock(return_value=remote_inspect_info)
        img_obj.populate_remote_inspect_info()
        db.make_remote_image = MagicMock(return_value=img_obj)
        db.has_image = MagicMock(return_value=None)
        util.skopeo_inspect = MagicMock(return_value=[])
        args = self.Args()
        args.image = image_name
        args.storage = 'docker'
        pull = Pull()
        pull.set_args(args)
        pull.be_utils.get_backend_from_string = MagicMock(return_value=db)
        util.skopeo_copy = MagicMock(return_value=None)
        pull.pull_image()


    def test_pull_by_digest_already_present(self):
        image_name = "docker.io/busybox@sha256:29f5d56d12684887bdfa50dcd29fc31eea4aaf4ad3bec43daf19026a7ce69912"
        db = DockerBackend()
        remote_img_obj = db._make_remote_image(image_name)
        remote_img_obj.remote_inspect = MagicMock(return_value=remote_inspect_info)
        remote_img_obj.populate_remote_inspect_info()
        db.make_remote_image = MagicMock(return_value=remote_img_obj)
        db._inspect_image = MagicMock(return_value=local_inspect_info)
        local_image_obj = db.inspect_image(image_name)
        db.has_image = MagicMock(return_value=local_image_obj)
        args = self.Args()
        args.image = image_name
        args.storage = 'docker'
        pull = Pull()
        pull.set_args(args)
        pull.be_utils.get_backend_from_string = MagicMock(return_value=db)
        pull.pull_image()


if __name__ == '__main__':
    unittest.main()
