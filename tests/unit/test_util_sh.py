import unittest
import os

from Atomic import util

class TestAtomicUtilSh(unittest.TestCase):

    def assertShSetEqual(self, a, b):
        self.assertEqual(sorted(a.split()), sorted(b.split()))

    def test_util_sh_set(self):
        self.assertShSetEqual(util.sh_set_add("foo bar", [ "baz", "bla" ]),
                              "foo bar baz bla")
        self.assertShSetEqual(util.sh_set_add("foo bar", [ "foo" ]),
                              "foo bar")
        self.assertShSetEqual(util.sh_set_del("foo bar", [ "foo" ]),
                              "bar")
        self.assertShSetEqual(util.sh_set_del("foo bar", [ "baz" ]),
                              "foo bar")

    def test_util_sh_modify_text(self):
        def uppercasify(old):
            return old.upper()

        # Non-existing setting causes a new entry with default
        self.assertEqual(util.sh_modify_var_in_text('', "VAR", uppercasify, "def"),
                         '\nVAR="DEF"\n')

        # Existing setting will be modified
        self.assertEqual(util.sh_modify_var_in_text('VAR="val"\n', "VAR", uppercasify),
                         'VAR="VAL"\n')

        # Two settings will both be modified
        self.assertEqual(util.sh_modify_var_in_text('VAR="val1"\nVAR="val2"\n', "VAR", uppercasify),
                         'VAR="VAL1"\nVAR="VAL2"\n')

        # Setting on partial line is recognized
        self.assertEqual(util.sh_modify_var_in_text('VAR="val"', "VAR", uppercasify),
                         'VAR="VAL"')

        # Setting with extra whitespace is recognized
        self.assertEqual(util.sh_modify_var_in_text('   VAR  =  "val"  \n', "VAR", uppercasify),
                         'VAR="VAL"\n')

        # Setting in a comment is not recognized
        self.assertEqual(util.sh_modify_var_in_text('# VAR="OLD"\n', "VAR", uppercasify),
                         '# VAR="OLD"\n\nVAR=""\n')

        # Setting without quotes around the value is not recognized
        self.assertEqual(util.sh_modify_var_in_text('VAR=OLD\n', "VAR", uppercasify),
                         'VAR=OLD\n\nVAR=""\n')

    def assertFileEqual(self, file, content):
        self.assertEqual(open(file, "r").read(), content)

    def test_util_sh_modify_file(self):
        file = os.path.join(os.environ["WORK_DIR"], "sh.conf")

        def uppercasify(old):
            return old.upper()

        # Non-existing file is treated as empty
        self.assertFalse(os.path.exists(file))
        util.sh_modify_var_in_file(file, "VAR", uppercasify, "def")
        self.assertFileEqual(file, '\nVAR="DEF"\n')

        # Existing file is modified in place as expected
        with open(file, "w") as f:
            f.write('VAR="val"\n')
        util.sh_modify_var_in_file(file, "VAR", uppercasify)
        self.assertFileEqual(file, 'VAR="VAL"\n')

if __name__ == '__main__':
    unittest.main()
