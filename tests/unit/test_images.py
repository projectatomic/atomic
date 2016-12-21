#pylint: skip-file
import unittest
from Atomic.backendutils import BackendUtils
from Atomic.backends._docker import DockerBackend
from Atomic.backends._ostree import OSTreeBackend
from Atomic.info import Info
from Atomic.images import Images
from Atomic.verify import Verify
from Atomic.objects.image import Image

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
_rhel_docker_inspect = {u'Comment': u'', u'Container': u'', u'DockerVersion': u'1.9.1', u'Parent': u'', u'Created': u'2016-10-26T12:02:33.368772Z', u'Config': {u'Tty': False, u'Cmd': [u'/bin/bash'], u'Volumes': None, u'Domainname': u'', u'WorkingDir': u'', u'Image': u'f6f6121b053b2312688c87d3a1d32d06a984dc01d2ea7738508a50581cddb6b4', u'Hostname': u'', u'StdinOnce': False, u'Labels': {u'com.redhat.component': u'rhel-server-docker', u'authoritative-source-url': u'registry.access.redhat.com', u'distribution-scope': u'public', u'Vendor': u'Red Hat, Inc.', u'Name': u'rhel7/rhel', u'Build_Host': u'rcm-img01.build.eng.bos.redhat.com', u'vcs-type': u'git', u'name': u'rhel7/rhel', u'vcs-ref': u'7eeaf203cf909c2c056fba7066db9c1073a28d97', u'release': u'45', u'Version': u'7.3', u'Architecture': u'x86_64', u'version': u'7.3', u'Release': u'45', u'vendor': u'Red Hat, Inc.', u'BZComponent': u'rhel-server-docker', u'build-date': u'2016-10-26T07:54:17.037911Z', u'com.redhat.build-host': u'ip-10-29-120-48.ec2.internal', u'architecture': u'x86_64'}, u'AttachStdin': False, u'User': u'', u'Env': [u'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin', u'container=docker'], u'Entrypoint': None, u'OnBuild': [], u'AttachStderr': False, u'AttachStdout': False, u'OpenStdin': False}, u'Author': u'Red Hat, Inc.', u'GraphDriver': {u'Data': {u'DeviceName': u'docker-253:2-5900125-a2bce97a4fd7ea12dce9865caa461ead8d1caf51ef452aba2f1b9d98efdf968f', u'DeviceSize': u'10737418240', u'DeviceId': u'623'}, u'Name': u'devicemapper'}, u'VirtualSize': 192508958, u'Os': u'linux', u'Architecture': u'amd64', u'RootFS': {u'Layers': [u'34d3e0e77091d9d51c6f70a7a7a4f7536aab214a55e02a8923af8f80cbe60d30', u'ccd6fc81ec49bd45f04db699401eb149b1945bb7292476b390ebdcdd7d975697'], u'Type': u'layers'}, u'ContainerConfig': {u'Tty': False, u'Cmd': None, u'Volumes': None, u'Domainname': u'', u'WorkingDir': u'', u'Image': u'', u'Hostname': u'', u'StdinOnce': False, u'Labels': None, u'AttachStdin': False, u'User': u'', u'Env': None, u'Entrypoint': None, u'OnBuild': None, u'AttachStderr': False, u'AttachStdout': False, u'OpenStdin': False}, u'Size': 192508958, u'RepoDigests': [u'registry.access.redhat.com/rhel7@sha256:da8a3e9297da7ccd1948366103d13c45b7e77489382351a777a7326004b63a21'], u'Id': u'f98706e16e41e56c4beaeea9fa77cd00fe35693635ed274f128876713afc0a1e', u'RepoTags': [u'registry.access.redhat.com/rhel7:latest']}
_rhel_version_result = 'IMAGE NAME                                       VERSION           IMAGE ID  \nregistry.access.redhat.com/rhel7:latest          rhel7/rhel-7.3-45 f98706e16e41\n'
_rhel_version_json = [{'Image': ['registry.access.redhat.com/rhel7:latest'], 'iid': 'f98706e16e41e56c4beaeea9fa77cd00fe35693635ed274f128876713afc0a1e', 'Version': '7.3-45'}]
_rhel_ostree_inspect = {'Created': 1480459483, 'RepoTags': ['registry.access.redhat.com/rhel7'], 'ImageId': 'da8a3e9297da7ccd1948366103d13c45b7e77489382351a777a7326004b63a21', 'OSTree-rev': 'a5840a53b233fdb936de8bcd35c77007b9af2d446ebabce6a2716772d6f089bd', 'Names': [], 'Id': 'da8a3e9297da7ccd1948366103d13c45b7e77489382351a777a7326004b63a21', 'Labels': {'name': 'rhel7/rhel', 'vendor': 'Red Hat, Inc.', 'authoritative-source-url': 'registry.access.redhat.com', 'version': '7.3', 'com.redhat.component': 'rhel-server-docker', 'distribution-scope': 'public', 'Name': 'rhel7/rhel', 'Architecture': 'x86_64', 'Version': '7.3', 'Vendor': 'Red Hat, Inc.', 'build-date': '2016-10-26T07:54:17.037911Z', 'com.redhat.build-host': 'ip-10-29-120-48.ec2.internal', 'Release': '45', 'BZComponent': 'rhel-server-docker', 'release': '45', 'vcs-type': 'git', 'Build_Host': 'rcm-img01.build.eng.bos.redhat.com', 'vcs-ref': '7eeaf203cf909c2c056fba7066db9c1073a28d97', 'architecture': 'x86_64'}, 'Version': 'registry.access.redhat.com/rhel7', 'ImageType': 'system'}
_rhel_ostree_version_result = 'IMAGE NAME                                VERSION                                 IMAGE ID  \nregistry.access.redhat.com/rhel7          registry.access.redhat.com/rhel7-7.3-45 da8a3e9297da\n'
_rhel_ostree_json = [{'Image': ['registry.access.redhat.com/rhel7'], 'iid': 'da8a3e9297da7ccd1948366103d13c45b7e77489382351a777a7326004b63a21', 'Version': '7.3-45'}]



@unittest.skipIf(no_mock, "Mock not found")
class TestInfo(unittest.TestCase):
    class Args():
        def __init__(self):
            self.storage = None
            self.force = False
            self.json = False
            self.debug = False

    def test_docker_info(self):
        db = DockerBackend()
        db._inspect_image = MagicMock(return_value=_centos_inspect_image)
        img_obj = db.inspect_image('docker.io/library/centos:latest')
        info = Info()
        args = self.Args()
        args.storage = 'docker'
        info.set_args(args)
        info.beu.get_backend_and_image_obj = MagicMock(return_value=(db, img_obj))
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
        info.beu.get_backend_and_image_obj = MagicMock(return_value=(ob, img_obj))
        result = info.info()
        self.assertEqual(result, _ostree_centos_result)

    def test_version_json_docker(self):
        db = DockerBackend()
        db._inspect_image = MagicMock(return_value=_rhel_docker_inspect)
        img_obj = db.inspect_image('registry.access.redhat.com/rhel7')
        info = Info()
        info.get_layer_objects = MagicMock(return_value=img_obj.layers)
        args = self.Args()
        args.storage = 'docker'
        args.images = 'registry.access.redhat.com/rhel7'
        info.set_args(args)
        results = info.dbus_version()
        self.assertEqual(results, _rhel_version_json)

    def test_version_json_ostree(self):
        ob = OSTreeBackend()
        ob.syscontainers.inspect_system_image = MagicMock(return_value=_rhel_ostree_inspect)
        img_obj = ob.inspect_image('registry.access.redhat.com/rhel7')
        info = Info()
        info.get_layer_objects = MagicMock(return_value=img_obj.layers)
        args = self.Args()
        args.storage = 'ostree'
        args.images = 'registry.access.redhat.com/rhel7'
        info.set_args(args)
        results = info.dbus_version()
        self.assertEqual(results, _rhel_ostree_json)


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
        args.filter = None
        images.set_args(args)
        return_value = images.display_all_image_info()
        self.assertEqual(return_value, 0)


remote_centos_inspect_latest = {'Layers': [u'sha256:08d48e6f1cff259389732d35307bb877215fa28867cdaff50c1dbd6e0b993c1f'], 'Name': 'docker.io/library/centos', 'Created': u'2016-11-02T19:52:09.463959047Z', 'Architecture': u'amd64', 'Os': u'linux', 'id': u'sha256:0584b3d2cf6d235ee310cf14b54667d889887b838d3f3d3033acd70fc3c48b8a', 'RepoTags': [u'5.11', u'5', u'6.6', u'6.7', u'6.8', u'6', u'7.0.1406', u'7.1.1503', u'7.2.1511', u'7', u'centos5.11', u'centos5', u'centos6.6', u'centos6.7', u'centos6.8', u'centos6', u'centos7.0.1406', u'centos7.1.1503', u'centos7.2.1511', u'centos7', u'latest'], 'DockerVersion': u'1.12.1', 'Labels': {u'build-date': u'20161102', u'vendor': u'CentOS', u'name': u'CentOS Base Image', u'license': u'GPLv2'}, 'Tag': 'latest', 'Digest': 'sha256:b2f9d1c0ff5f87a4743104d099a3d561002ac500db1b9bfa02a783a46e0d366c'}
local_centos_inspect_old = {'Id': '16e9fdecc1febc87fb1ca09271009cf5f28eb8d4aec5515922ef298c145a6726', 'RepoDigests': ['docker.io/centos@sha256:7793b39617b28c6cd35774c00383b89a1265f3abf6efcaf0b8f4aafe4e0662d2'], 'Parent': '', 'GraphDriver': {'Name': 'devicemapper', 'Data': {'DeviceSize': '10737418240', 'DeviceName': 'docker-253:2-5900125-3fb5b406e6a53142129237c9e2c3a1ce8b6cf269b5f8071fcd62107c41544cd2', 'DeviceId': '779'}}, 'Created': '2016-08-30T18:20:19.39890162Z', 'Comment': '', 'DockerVersion': '1.12.1', 'VirtualSize': 210208812, 'Author': 'The CentOS Project <cloud-ops@centos.org> - ami_creator', 'Os': 'linux', 'RootFS': {'Type': 'layers', 'Layers': ['5fa0fa02637842ab1ddc8b3a17b86691c87c87d20800e6a95a113343f6ffd84c']}, 'Container': 'a5b0819aa82c224095e1a18e9df0776a7b38d32bacca073f054723b65fb54f0e', 'Architecture': 'amd64', 'RepoTags': ['docker.io/centos:centos7.0.1406'], 'Config': {'Labels': {}, 'Entrypoint': None, 'StdinOnce': False, 'OnBuild': None, 'Env': ['PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'], 'Volumes': None, 'Cmd': None, 'User': '', 'AttachStdin': False, 'AttachStderr': False, 'AttachStdout': False, 'WorkingDir': '', 'Tty': False, 'Image': '20ae10d641a0af6f25ceaa75fdcf591d171e3c521a54a3f3a2868b602d735e11', 'Hostname': 'a5b0819aa82c', 'Domainname': '', 'OpenStdin': False}, 'Size': 210208812, 'ContainerConfig': {'Labels': {}, 'Entrypoint': None, 'StdinOnce': False, 'OnBuild': None, 'Env': ['PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'], 'Volumes': None, 'Cmd': ['/bin/sh', '-c', '#(nop) ADD file:6a409eac27f0c7e04393da096dbeff01b929405e79b15222a0dc06a2084d3df3 in / '], 'User': '', 'AttachStdin': False, 'AttachStderr': False, 'AttachStdout': False, 'WorkingDir': '', 'Tty': False, 'Image': '20ae10d641a0af6f25ceaa75fdcf591d171e3c521a54a3f3a2868b602d735e11', 'Hostname': 'a5b0819aa82c', 'Domainname': '', 'OpenStdin': False}}
docker_dbus_result = [{'differs': False, 'local_version': '0584b3d2cf6d235ee310cf14b54667d889887b838d3f3d3033acd70fc3c48b8a', 'name': 'centos', 'remote_version': '0584b3d2cf6d235ee310cf14b54667d889887b838d3f3d3033acd70fc3c48b8a'}]


@unittest.skipIf(no_mock, "Mock not found")
class TestVerify(unittest.TestCase):
    class Args():
        def __init__(self):
            self.storage = None
            self.debug = False
            self.name = None
            self.image = None

    def test_verify_docker_same(self):
        with patch('Atomic.backendutils.BackendUtils.get_backend_and_image_obj') as mockobj:
            args = self.Args()
            args.storage = 'docker'
            args.image = 'docker.io/library/centos:latest'
            db = DockerBackend()
            db._inspect_image = MagicMock(return_value=_centos_inspect_image)
            local_image_object = db.inspect_image(args.image)
            mockobj.return_value = (db, local_image_object)
            v = Verify()
            v.set_args(args)
            Image.remote_inspect = MagicMock(return_value=remote_centos_inspect_latest)
            self.assertEqual(v.verify_dbus(), docker_dbus_result)

    def test_verify_docker_diff(self):
        with patch('Atomic.backendutils.BackendUtils.get_backend_and_image_obj') as mockobj:
            args = self.Args()
            args.storage = 'docker'
            args.image = 'docker.io/library/centos:centos7.0.1406'
            db = DockerBackend()
            db._inspect_image = MagicMock(return_value=local_centos_inspect_old)
            local_image_object = db.inspect_image(args.image)
            mockobj.return_value = (db, local_image_object)
            v = Verify()
            v.set_args(args)
            Image.remote_inspect = MagicMock(return_value=remote_centos_inspect_latest)
            self.assertNotEqual(v.verify_dbus(), docker_dbus_result)

    def test_verify_ostree_same(self):
        # I hit some issue with syscontainers here.  Will leave until that issue
        # can be resolved with guiseppe
        pass
