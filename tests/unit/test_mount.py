import unittest

from Atomic import mount


class TestAtomicMount(unittest.TestCase):
    def test_mount_excepts_unknown_backend(self):
        def mock_info():
            return {'Driver': 'foobardriver'}
        with mount.DockerMount('foobar') as m:
            m.d.info = mock_info
            exp = 'Atomic mount is not supported on the foobardriver docker ' \
                  'storage backend.'

            # assertRaisesRegexp was deprecated by assertRaisesRegex.
            # If it is present, prefer assertRaisesRegex.
            if hasattr(self, 'assertRaisesRegex'):
                assertRaisesRegex = getattr(self, "assertRaisesRegex")
            else:
                assertRaisesRegex = getattr(self, "assertRaisesRegexp")
            assertRaisesRegex(mount.MountError, exp, m.mount, 'fedora:22')
            assertRaisesRegex(mount.MountError, exp, m.unmount)

    def test_default_options(self):
        with mount.DockerMount('foobar') as m:
            o = m.default_options([], default_con='foobar_context',
                                  default_opt=['foo', 'bar'])
            self.assertEqual(o, ['foo', 'bar', 'context="foobar_context"'])

    def test_default_options_override_defaults(self):
        with mount.DockerMount('foobar') as m:
            o = m.default_options(['override', 'opts'],
                                  default_con='foobar_context',
                                  default_opt=['will not appear'])
            self.assertEqual(o, ['override', 'opts', 'context="foobar_context"'])

    def test_default_options_no_surplus_context(self):
        with mount.DockerMount('foobar') as m:
            o = m.default_options(['ro', 'context="foobang_context"'],
                                  default_con='foobar_context')
            self.assertEqual(o, ['ro', 'context="foobang_context"'])

if __name__ == '__main__':
    unittest.main()
