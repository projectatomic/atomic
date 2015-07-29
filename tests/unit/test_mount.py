import unittest

from Atomic import mount


class TestAtomicMount(unittest.TestCase):
    def test_mount_excepts_unknown_backend(self):
        def mock_info():
            return {'Driver': 'foobardriver'}
        m = mount.DockerMount('foobar')
        m.client.info = mock_info
        exp = 'Atomic mount is not supported on the foobardriver docker ' \
              'storage backend.'
        self.assertRaisesRegexp(mount.MountError, exp, m.mount, 'fedora:22')
        self.assertRaisesRegexp(mount.MountError, exp, m.unmount)

    def test_default_options(self):
        m = mount.DockerMount('foobar')
        o = m._default_options([], default_con='foobar_context',
                               default_options=['foo', 'bar'])
        self.assertEqual(o, ['foo', 'bar', 'context="foobar_context"'])

    def test_default_options_override_defaults(self):
        m = mount.DockerMount('foobar')
        o = m._default_options(['override', 'opts'],
                               default_con='foobar_context',
                               default_options=['will not appear'])
        self.assertEqual(o, ['override', 'opts', 'context="foobar_context"'])

    def test_default_options_no_surplus_context(self):
        m = mount.DockerMount('foobar')
        o = m._default_options(['ro', 'context="foobang_context"'],
                               default_con='foobar_context')
        self.assertEqual(o, ['ro', 'context="foobang_context"'])

    def test_not_implemented_container_backend(self):
        m = mount.Mount('foobar')
        self.assertRaises(NotImplementedError, m.mount, '')
        self.assertRaises(NotImplementedError, m.unmount)


if __name__ == '__main__':
    unittest.main()
