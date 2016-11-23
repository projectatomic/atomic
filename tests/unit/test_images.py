#pylint: skip-file
import unittest
from Atomic.backendutils import BackendUtils
from Atomic.backends._docker import DockerBackend
from Atomic.backends._ostree import OSTreeBackend
from Atomic.info import Info
from Atomic.images import Images

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


_centos_inspect_image = {u'Comment': u'', u'Container': u'58aeaa4866c2845b48ab998b7cba3856a9fb64a681f92544cb035b85066b5102', u'DockerVersion': u'1.12.1', u'Parent': u'', u'Created': u'2016-11-02T19:52:09.463959047Z', u'Config': {u'Tty': False, u'Cmd': [u'/bin/bash'], u'Volumes': None, u'Domainname': u'', u'WorkingDir': u'', u'Image': u'5a2725191d75eb64e9b7c969cd23d8c67c6e8af9979e521a417bbfa34434fb83', u'Hostname': u'd6dcf178f680', u'StdinOnce': False, u'Labels': {u'build-date': u'20161102', u'vendor': u'CentOS', u'name': u'CentOS Base Image', u'license': u'GPLv2'}, u'AttachStdin': False, u'User': u'', u'Env': [u'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'], u'Entrypoint': None, u'OnBuild': None, u'AttachStderr': False, u'AttachStdout': False, u'OpenStdin': False}, u'Author': u'https://github.com/CentOS/sig-cloud-instance-images', u'GraphDriver': {u'Data': {u'DeviceName': u'docker-253:1-20984667-e3af0c61256f885331fb1a3adc27ea509a10ba9a0ba9175c1a149f81bddcd30d', u'DeviceSize': u'10737418240', u'DeviceId': u'2'}, u'Name': u'devicemapper'}, u'VirtualSize': 196509652, u'Os': u'linux', u'Architecture': u'amd64', u'ContainerConfig': {u'Tty': False, u'Cmd': [u'/bin/sh', u'-c', u'#(nop) ', u'CMD ["/bin/bash"]'], u'Volumes': None, u'Domainname': u'', u'WorkingDir': u'', u'Image': u'5a2725191d75eb64e9b7c969cd23d8c67c6e8af9979e521a417bbfa34434fb83', u'Hostname': u'd6dcf178f680', u'StdinOnce': False, u'Labels': {u'build-date': u'20161102', u'vendor': u'CentOS', u'name': u'CentOS Base Image', u'license': u'GPLv2'}, u'AttachStdin': False, u'User': u'', u'Env': [u'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'], u'Entrypoint': None, u'OnBuild': None, u'AttachStderr': False, u'AttachStdout': False, u'OpenStdin': False}, u'Size': 196509652, u'RepoDigests': [u'docker.io/centos@b2f9d1c0ff5f87a4743104d099a3d561002ac500db1b9bfa02a783a46e0d366c'], u'Id': u'0584b3d2cf6d235ee310cf14b54667d889887b838d3f3d3033acd70fc3c48b8a', u'RepoTags': [u'docker.io/centos:latest']}
_docker_centos_result = 'Image Name: docker.io/library/centos:latest\nbuild-date: 20161102\nlicense: GPLv2\nname: CentOS Base Image\nvendor: CentOS\n'
_ostree_centos_result = 'Image Name: docker.io/library/centos:latest\nbuild-date: 20161102\nlicense: GPLv2\nname: CentOS Base Image\nvendor: CentOS\n\n\nTemplate variables with default value, but overridable with --set:\nRUN_DIRECTORY: {SET_BY_OS}\nSTATE_DIRECTORY: {SET_BY_OS}\n'
_centos_ostree_inspect = {'Version': 'centos', 'Labels': {u'build-date': u'20161102', u'vendor': u'CentOS', u'name': u'CentOS Base Image', u'license': u'GPLv2'}, 'Names': [], 'Created': 1480352808, 'OSTree-rev': 'd2122127d30f94ae12ebe5afa542abdb1870201b0b9750bae3ceb74aa6ed18e6', 'RepoTags': ['centos'], 'Id': u'b2f9d1c0ff5f87a4743104d099a3d561002ac500db1b9bfa02a783a46e0d366c', 'ImageType': 'system', 'ImageId': u'b2f9d1c0ff5f87a4743104d099a3d561002ac500db1b9bfa02a783a46e0d366c'}


@unittest.skipIf(no_mock, "Mock not found")
class TestInfo(unittest.TestCase):
    class Args():
        def __init__(self):
            self.storage = None
            self.force = False
            self.json = False

    def test_docker_info(self):
        db = DockerBackend()
        db._inspect_image = MagicMock(return_value=_centos_inspect_image)
        img_obj = db.inspect_image('docker.io/library/centos:latest')
        info = Info()
        args = self.Args()
        args.storage = 'docker'
        info.set_args(args)
        info.beu.get_backend_and_image = MagicMock(return_value=(db, img_obj))
        result = info.info()
        self.assertEqual(result, _docker_centos_result)

    def test_ostree_info(self):
        ob = OSTreeBackend()
        ob.syscontainers.inspect_system_image = MagicMock(return_value=_centos_ostree_inspect)
        img_obj = ob.inspect_image('docker.io/library/centos:latest')
        img_obj._template_variables_set = {'RUN_DIRECTORY': '{SET_BY_OS}', 'STATE_DIRECTORY': '{SET_BY_OS}'}
        img_obj._template_variables_unset = {}
        info = Info()
        args = self.Args()
        args.storage = 'ostree'
        info.set_args(args)
        info.beu.get_backend_and_image = MagicMock(return_value=(ob, img_obj))
        result = info.info()
        self.assertEqual(result, _ostree_centos_result)


_docker_images = [{'VirtualSize': 196509652, 'Labels': {'vendor': 'CentOS', 'license': 'GPLv2', 'build-date': '20161102', 'name': 'CentOS Base Image'}, 'RepoTags': ['docker.io/centos:latest'], 'ParentId': '', 'Id': '0584b3d2cf6d235ee310cf14b54667d889887b838d3f3d3033acd70fc3c48b8a', 'Size': 196509652, 'Created': 1478116329, 'RepoDigests': ['docker.io/centos@sha256:b2f9d1c0ff5f87a4743104d099a3d561002ac500db1b9bfa02a783a46e0d366c']}, {'VirtualSize': 1093484, 'Labels': {}, 'RepoTags': ['docker.io/busybox:latest'], 'ParentId': '', 'Id': 'e02e811dd08fd49e7f6032625495118e63f597eb150403d02e3238af1df240ba', 'Size': 1093484, 'Created': 1475874238, 'RepoDigests': ['docker.io/busybox@sha256:29f5d56d12684887bdfa50dcd29fc31eea4aaf4ad3bec43daf19026a7ce69912']}]
_system_images = [{'Labels': {'vendor': 'CentOS', 'license': 'GPLv2', 'build-date': '20161102', 'name': 'CentOS Base Image'}, 'ImageId': 'b2f9d1c0ff5f87a4743104d099a3d561002ac500db1b9bfa02a783a46e0d366c', 'Version': 'centos:latest', 'OSTree-rev': 'd2122127d30f94ae12ebe5afa542abdb1870201b0b9750bae3ceb74aa6ed18e6', 'ImageType': 'system', 'Id': 'b2f9d1c0ff5f87a4743104d099a3d561002ac500db1b9bfa02a783a46e0d366c', 'Created': 1480352808, 'Names': [], 'RepoTags': ['centos:latest']}, {'Labels': {}, 'ImageId': '29f5d56d12684887bdfa50dcd29fc31eea4aaf4ad3bec43daf19026a7ce69912', 'Version': 'busybox:latest', 'OSTree-rev': 'f0cbd09116e348782fc353f99db2b111a59fdf929e9a0180f3a8450c145ed8bc', 'ImageType': 'system', 'Id': '29f5d56d12684887bdfa50dcd29fc31eea4aaf4ad3bec43daf19026a7ce69912', 'Created': 1480348080, 'Names': [], 'RepoTags': ['busybox:latest']}]

@unittest.skipIf(no_mock, "Mock not found")
class TestImages(unittest.TestCase):
    class Args():
        def __init__(self):
            self.storage = None
            self.force = False
            self.json = False
            self.debug = False
            self.name = None
            self.image = None
            self.all = False

    def test_images(self):
        db = DockerBackend()
        db._inspect_image = MagicMock(return_value=_docker_images)
        ob = OSTreeBackend()
        ob.syscontainers.get_system_images = MagicMock(return_value=_system_images)
        images = Images()
        args = self.Args()
        args.storage = 'docker'
        args.json = True
        images.set_args(args)
        return_value = images.display_all_image_info()
        self.assertEqual(return_value, 0)

