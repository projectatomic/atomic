#pylint: skip-file
import unittest
import selinux
import sys
from Atomic import util
from Atomic.backends._docker import DockerBackend
import time
import os
import re

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

def _new_enough():
    py_version = sys.version_info
    if (py_version.major, py_version.minor, py_version.micro) >= (2, 7, 6):
        return True
    return False

new_enough = _new_enough()

if no_mock:
    # If there is no mock, we need need to create a fake
    # patch decorator
    def fake_patch(a, new=''):
        def foo(func):
            def wrapper(*args, **kwargs):
                ret = func(*args, **kwargs)
                return ret
            return wrapper
        return foo

    patch = fake_patch


class TestAtomicUtil(unittest.TestCase):

    def test_image_by_name(self):
        matches = util.image_by_name('atomic-test-1')
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['Labels']['Name'],
                         'atomic-test-1')

    def test_image_by_name_glob(self):
        matches = util.image_by_name('atomic-test-*')
        self.assertTrue(len(matches) > 2)
        self.assertTrue(all([m['Labels']['Name'].startswith('atomic-test-')
                             for m in matches]))

    def test_image_by_name_registry_match(self):
        matches = util.image_by_name('/centos:latest')
        self.assertTrue(len(matches) == 1)

    def test_image_by_name_no_match(self):
        matches = util.image_by_name('this is not a real image name')
        self.assertTrue(len(matches) == 0)

    def test_default_container_context(self):
        default = util.default_container_context()
        if selinux.is_selinux_enabled():
            # newer policies use container_file_t
            self.assertTrue(default in
                            ['system_u:object_r:container_file_t:s0',
                             'system_u:object_r:svirt_sandbox_file_t:s0'])
        else:
            self.assertEqual(default, '')

    def test_check_call(self):
        exception_raised = False
        try:
            util.check_call(['/usr/bin/does_not_exist'])
        except util.FileNotFound:
            exception_raised = True
        self.assertTrue(exception_raised)

    def test_call(self):
        exception_raised = False
        try:
            util.call(['/usr/bin/does_not_exist'])
        except util.FileNotFound:
            exception_raised = True
        self.assertTrue(exception_raised)

    def test_check_output(self):
        exception_raised = False
        try:
            util.check_call(['/usr/bin/does_not_exist'])
        except util.FileNotFound:
            exception_raised = True
        self.assertTrue(exception_raised)

    def test_decompose(self):
        images = [('docker.io/library/busybox', ('docker.io', 'library','busybox', 'latest', '')),
                  ('docker.io/library/foobar/busybox', ('docker.io', 'library/foobar', 'busybox', 'latest', '')),
                  ('docker.io/library/foobar/busybox:2.1', ('docker.io', 'library/foobar', 'busybox', '2.1', '')),
                  ('docker.io/busybox:2.1', ('docker.io', 'library', 'busybox', '2.1', '')),
                  ('docker.io/busybox', ('docker.io', 'library', 'busybox', 'latest', '')),
                  ('docker.io:5000/busybox', ('docker.io:5000', '', 'busybox', 'latest', '')),
                  ('docker.io:5000/library/busybox:2.1', ('docker.io:5000', 'library', 'busybox', '2.1', '')),
                  ('busybox', ('', '', 'busybox', 'latest', '')),
                  ('busybox:2.1', ('', '', 'busybox', '2.1', '')),
                  ('library/busybox', ('', 'library', 'busybox', 'latest', '')),
                  ('library/busybox:2.1', ('', 'library', 'busybox', '2.1', '')),
                  ('registry.access.redhat.com/rhel7:latest', ('registry.access.redhat.com', '', 'rhel7', 'latest', '')),
                  ('registry.access.redhat.com/rhel7', ('registry.access.redhat.com', '', 'rhel7', 'latest', '')),
                  ('fedora@sha256:64a02df6aac27d1200c2572fe4b9949f1970d05f74d367ce4af994ba5dc3669e', ('', '', 'fedora', '', 'sha256:64a02df6aac27d1200c2572fe4b9949f1970d05f74d367ce4af994ba5dc3669e')),
                  ('docker.io/library/fedora@sha256:64a02df6aac27d1200c2572fe4b9949f1970d05f74d367ce4af994ba5dc3669e', ('docker.io', 'library', 'fedora', '', 'sha256:64a02df6aac27d1200c2572fe4b9949f1970d05f74d367ce4af994ba5dc3669e')),
                  ('docker.io/fedora@sha256:64a02df6aac27d1200c2572fe4b9949f1970d05f74d367ce4af994ba5dc3669e', ('docker.io', 'library', 'fedora', '', 'sha256:64a02df6aac27d1200c2572fe4b9949f1970d05f74d367ce4af994ba5dc3669e'))
                  ]

        for image in images:
            self.assertEqual(util.Decompose(image[0]).all, image[1])

    @unittest.skipUnless(new_enough, "Requires 2.7.6 or newer")
    def test_valid_uri(self):
        valid_uris = ['example.com', 'example.com:5000', 'example.US.com', 'example.com/image/name:version1', 'example.com:5000/foo/bar/image:tag', 'example_inc.com']
        invalid_uris = ['example.com/Image/name', 'example.com/image(name):latest', 'example.com/foo_bar', 'example[us].com', 'example.com#foo/bar']
        for uri in valid_uris:
            self.assertTrue(util.is_valid_image_uri(uri))

        for uri in invalid_uris:
            exception_raised = False
            try:
                util.is_valid_image_uri(uri)
            except ValueError:
                exception_raised = True
            self.assertTrue(exception_raised)

    def test_set_proxy_default(self):
        # Make the test call
        proxies = util.set_proxy()
        # ensure each expected item exists
        for item in ('http', 'https', 'no_proxy'):
            self.assertIn(item, proxies.keys())

    def test_set_proxy_with_items(self):
        orig_environ = os.environ
        # Set all three
        for item in ('HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY'):
            os.environ[item] = item

        # Make the test call
        proxies = util.set_proxy()

        # Check each is set
        for key, val in (
                ('http', 'HTTP_PROXY'),
                ('https', 'HTTPS_PROXY'),
                ('no_proxy', 'NO_PROXY')):
            self.assertEquals(val, proxies[key])

        # Reset environ back to the original
        os.environ = orig_environ

    def test_get_proxy_defaults(self):
        proxies = util.get_proxy()
        # ensure each expected item exists
        for item in ('http', 'https', 'no_proxy'):
            self.assertIn(item, proxies.keys())

    def test_get_proxy_with_items(self):
        orig_environ = os.environ
        # Set all three
        for item in ('HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY'):
            os.environ[item] = item

        # Make the test call
        proxies = util.get_proxy()

        # Check each is set
        for key, val in (
                ('http', 'HTTP_PROXY'),
                ('https', 'HTTPS_PROXY'),
                ('no_proxy', 'NO_PROXY')):
            self.assertEquals(val, proxies[key])

        # Reset environ back to the original
        os.environ = orig_environ

    def test_get_all_known_process_capabilities(self):
        capabilities = util.get_all_known_process_capabilities()
        for item in ['CAP_CHOWN', 'CAP_SYS_ADMIN', 'CAP_MKNOD']:
            self.assertIn(item, capabilities)

        # Check that all the capabilities held by PID 1 are known.
        with open('/proc/1/status', 'r') as f:
            content = f.read()
            bounding_set = re.search( r'CapBnd:\t(.*)\n', content, re.M|re.I).group(1)
            out = util.check_output(['capsh', '--decode=%s' % bounding_set]).decode()
            out = str(out.split("=")[1])
            for i in out.strip().split(','):
                if not i[0].isdigit():
                    self.assertIn(i.upper(), capabilities)


class MockIO(object):
    original_data = {"install_test": [{"install_date": "2017-03-22 17:19:41", "id": "49779293ca711789a77bbdc35547a6b9ecb193a51b4e360fea95c4d206605d18"}]}
    new_data_fq = [{"install_date": "2017-04-22 17:19:41","id": "16e9fdecc1febc87fb1ca09271009cf5f28eb8d4aec5515922ef298c145a6726"}]
    new_data_name= [{"install_date": "2017-04-22 17:19:41","id": "16e9fdecc1febc87fb1ca09271009cf5f28eb8d4aec5515922ef298c145a6726"}]
    install_data = original_data

    @classmethod
    def read_mock(cls):
        return cls.install_data

    @classmethod
    def write_mock(cls, val):
        cls.install_data = val

    @classmethod
    def reset_data(cls):
        cls.install_data = cls.original_data

    @classmethod
    def grow_data(cls, var_name, name):
        cls.install_data[name] = getattr(cls, var_name)

local_centos_inspect = {'Id': '16e9fdecc1febc87fb1ca09271009cf5f28eb8d4aec5515922ef298c145a6726', 'RepoDigests': ['docker.io/centos@sha256:7793b39617b28c6cd35774c00383b89a1265f3abf6efcaf0b8f4aafe4e0662d2'], 'Parent': '', 'GraphDriver': {'Name': 'devicemapper', 'Data': {'DeviceSize': '10737418240', 'DeviceName': 'docker-253:2-5900125-3fb5b406e6a53142129237c9e2c3a1ce8b6cf269b5f8071fcd62107c41544cd2', 'DeviceId': '779'}}, 'Created': '2016-08-30T18:20:19.39890162Z', 'Comment': '', 'DockerVersion': '1.12.1', 'VirtualSize': 210208812, 'Author': 'The CentOS Project <cloud-ops@centos.org> - ami_creator', 'Os': 'linux', 'RootFS': {'Type': 'layers', 'Layers': ['5fa0fa02637842ab1ddc8b3a17b86691c87c87d20800e6a95a113343f6ffd84c']}, 'Container': 'a5b0819aa82c224095e1a18e9df0776a7b38d32bacca073f054723b65fb54f0e', 'Architecture': 'amd64', 'RepoTags': ['docker.io/centos:centos7.0.1406'], 'Config': {'Labels': {}, 'Entrypoint': None, 'StdinOnce': False, 'OnBuild': None, 'Env': ['PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'], 'Volumes': None, 'Cmd': None, 'User': '', 'AttachStdin': False, 'AttachStderr': False, 'AttachStdout': False, 'WorkingDir': '', 'Tty': False, 'Image': '20ae10d641a0af6f25ceaa75fdcf591d171e3c521a54a3f3a2868b602d735e11', 'Hostname': 'a5b0819aa82c', 'Domainname': '', 'OpenStdin': False}, 'Size': 210208812, 'ContainerConfig': {'Labels': {}, 'Entrypoint': None, 'StdinOnce': False, 'OnBuild': None, 'Env': ['PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'], 'Volumes': None, 'Cmd': ['/bin/sh', '-c', '#(nop) ADD file:6a409eac27f0c7e04393da096dbeff01b929405e79b15222a0dc06a2084d3df3 in / '], 'User': '', 'AttachStdin': False, 'AttachStderr': False, 'AttachStdout': False, 'WorkingDir': '', 'Tty': False, 'Image': '20ae10d641a0af6f25ceaa75fdcf591d171e3c521a54a3f3a2868b602d735e11', 'Hostname': 'a5b0819aa82c', 'Domainname': '', 'OpenStdin': False}}
rhel_docker_inspect = {u'Comment': u'', u'Container': u'', u'DockerVersion': u'1.9.1', u'Parent': u'', u'Created': u'2016-10-26T12:02:33.368772Z', u'Config': {u'Tty': False, u'Cmd': [u'/bin/bash'], u'Volumes': None, u'Domainname': u'', u'WorkingDir': u'', u'Image': u'f6f6121b053b2312688c87d3a1d32d06a984dc01d2ea7738508a50581cddb6b4', u'Hostname': u'', u'StdinOnce': False, u'Labels': {u'com.redhat.component': u'rhel-server-docker', u'authoritative-source-url': u'registry.access.redhat.com', u'distribution-scope': u'public', u'Vendor': u'Red Hat, Inc.', u'Name': u'rhel7/rhel', u'Build_Host': u'rcm-img01.build.eng.bos.redhat.com', u'vcs-type': u'git', u'name': u'rhel7/rhel', u'vcs-ref': u'7eeaf203cf909c2c056fba7066db9c1073a28d97', u'release': u'45', u'Version': u'7.3', u'Architecture': u'x86_64', u'version': u'7.3', u'Release': u'45', u'vendor': u'Red Hat, Inc.', u'BZComponent': u'rhel-server-docker', u'build-date': u'2016-10-26T07:54:17.037911Z', u'com.redhat.build-host': u'ip-10-29-120-48.ec2.internal', u'architecture': u'x86_64'}, u'AttachStdin': False, u'User': u'', u'Env': [u'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin', u'container=docker'], u'Entrypoint': None, u'OnBuild': [], u'AttachStderr': False, u'AttachStdout': False, u'OpenStdin': False}, u'Author': u'Red Hat, Inc.', u'GraphDriver': {u'Data': {u'DeviceName': u'docker-253:2-5900125-a2bce97a4fd7ea12dce9865caa461ead8d1caf51ef452aba2f1b9d98efdf968f', u'DeviceSize': u'10737418240', u'DeviceId': u'623'}, u'Name': u'devicemapper'}, u'VirtualSize': 192508958, u'Os': u'linux', u'Architecture': u'amd64', u'RootFS': {u'Layers': [u'34d3e0e77091d9d51c6f70a7a7a4f7536aab214a55e02a8923af8f80cbe60d30', u'ccd6fc81ec49bd45f04db699401eb149b1945bb7292476b390ebdcdd7d975697'], u'Type': u'layers'}, u'ContainerConfig': {u'Tty': False, u'Cmd': None, u'Volumes': None, u'Domainname': u'', u'WorkingDir': u'', u'Image': u'', u'Hostname': u'', u'StdinOnce': False, u'Labels': None, u'AttachStdin': False, u'User': u'', u'Env': None, u'Entrypoint': None, u'OnBuild': None, u'AttachStderr': False, u'AttachStdout': False, u'OpenStdin': False}, u'Size': 192508958, u'RepoDigests': [u'registry.access.redhat.com/rhel7@sha256:da8a3e9297da7ccd1948366103d13c45b7e77489382351a777a7326004b63a21'], u'Id': u'f98706e16e41e56c4beaeea9fa77cd00fe35693635ed274f128876713afc0a1e', u'RepoTags': [u'registry.access.redhat.com/rhel7:latest']}


@unittest.skipIf(no_mock, "Mock not found")
class InstallData(unittest.TestCase):

    class Args():
        def __init__(self):
            self.storage = None
            self.debug = False
            self.name = None
            self.image = None

    @patch('Atomic.util.InstallData.read_install_data', new=MockIO.read_mock)
    @patch('Atomic.util.InstallData.write_install_data', new=MockIO.write_mock)
    def test_read(self):
        MockIO.reset_data()
        self.assertEqual(util.InstallData.read_install_data(), MockIO.install_data)

    @patch('Atomic.util.InstallData.read_install_data', new=MockIO.read_mock)
    @patch('Atomic.util.InstallData.write_install_data', new=MockIO.write_mock)
    def test_write(self):
        MockIO.reset_data()
        install_data = util.InstallData.read_install_data()
        install_data['docker.io/library/centos:latest'] = MockIO.new_data_fq
        util.InstallData.write_install_data(install_data)
        self.assertTrue('docker.io/library/centos:latest' in util.InstallData.read_install_data())

    @patch('Atomic.util.InstallData.read_install_data', new=MockIO.read_mock)
    @patch('Atomic.util.InstallData.write_install_data', new=MockIO.write_mock)
    def test_get_install_name_by_id(self):
        MockIO.reset_data()
        MockIO.grow_data('new_data_fq', 'docker.io/library/centos:latest')
        self.assertEqual(util.InstallData.get_install_name_by_id('16e9fdecc1febc87fb1ca09271009cf5f28eb8d4aec5515922ef298c145a6726', install_data=MockIO.install_data), 'docker.io/library/centos:latest')

    @patch('Atomic.util.InstallData.read_install_data', new=MockIO.read_mock)
    @patch('Atomic.util.InstallData.write_install_data', new=MockIO.write_mock)
    def test_fail_get_install_name_by_id(self):
        MockIO.reset_data()
        self.assertRaises(ValueError, util.InstallData.get_install_name_by_id, 1, MockIO.install_data)

    @patch('Atomic.util.InstallData.read_install_data', new=MockIO.read_mock)
    @patch('Atomic.util.InstallData.write_install_data', new=MockIO.write_mock)
    def test_image_installed_name(self):
        MockIO.reset_data()
        MockIO.grow_data('new_data_fq', 'docker.io/library/centos:latest')
        args = self.Args()
        args.storage = 'docker'
        args.image = 'docker.io/library/centos:latest'
        db = DockerBackend()
        db._inspect_image = MagicMock(return_value=local_centos_inspect)
        local_image_object = db.inspect_image(args.image)
        self.assertTrue(util.InstallData.image_installed(local_image_object))

    @patch('Atomic.util.InstallData.read_install_data', new=MockIO.read_mock)
    @patch('Atomic.util.InstallData.write_install_data', new=MockIO.write_mock)
    def test_image_installed_id(self):
        MockIO.reset_data()
        MockIO.grow_data('new_data_fq', '16e9fdecc1febc87fb1ca09271009cf5f28eb8d4aec5515922ef298c145a6726')
        args = self.Args()
        args.storage = 'docker'
        args.image = 'docker.io/library/centos:latest'
        db = DockerBackend()
        db._inspect_image = MagicMock(return_value=local_centos_inspect)
        local_image_object = db.inspect_image(args.image)
        self.assertTrue(util.InstallData.image_installed(local_image_object))

    @patch('Atomic.util.InstallData.read_install_data', new=MockIO.read_mock)
    @patch('Atomic.util.InstallData.write_install_data', new=MockIO.write_mock)
    def test_image_not_installed(self):
        MockIO.reset_data()
        args = self.Args()
        args.storage = 'docker'
        args.image = 'registry.access.redhat.com/rhel7'
        db = DockerBackend()
        db._inspect_image = MagicMock(return_value=rhel_docker_inspect)
        local_image_object = db.inspect_image(args.image)
        self.assertFalse(util.InstallData.image_installed(local_image_object))


if __name__ == '__main__':
    unittest.main()
