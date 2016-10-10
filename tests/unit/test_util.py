import unittest
import selinux

from Atomic import util


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
        exp = ('system_u:object_r:svirt_sandbox_file_t:s0' if
               selinux.is_selinux_enabled() else '')
        self.assertEqual(exp, util.default_container_context())

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
        images = [('docker.io/library/busybox', ('docker.io', 'library','busybox', 'latest')),
                  ('docker.io/library/foobar/busybox', ('docker.io', 'library/foobar', 'busybox', 'latest')),
                  ('docker.io/library/foobar/busybox:2.1', ('docker.io', 'library/foobar', 'busybox', '2.1')),
                  ('docker.io/busybox:2.1', ('docker.io', 'library', 'busybox', '2.1')),
                  ('docker.io/busybox', ('docker.io', 'library', 'busybox', 'latest')),
                  ('busybox', ('', '', 'busybox', 'latest')),
                  ('busybox:2.1', ('', '', 'busybox', '2.1')),
                  ('library/busybox', ('', 'library', 'busybox', 'latest')),
                  ('library/busybox:2.1', ('', 'library', 'busybox', '2.1')),
                  ('registry.access.redhat.com/rhel7:latest', ('registry.access.redhat.com', '', 'rhel7', 'latest')),
                  ('registry.access.redhat.com/rhel7', ('registry.access.redhat.com', '', 'rhel7', 'latest'))
                  ]

        for image in images:
            self.assertEqual(util.decompose(image[0]), image[1])


if __name__ == '__main__':
    unittest.main()
