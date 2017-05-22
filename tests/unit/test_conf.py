#pylint: skip-file
import os
import unittest

import yaml


class TestAtomicUnit(unittest.TestCase):
    """
    Checks that the configuration file provided is valid.
    """

    def setUp(self):
        """
        Provide the conf file contents freshly for each test.
        """
        self.conf = open(os.path.sep.join(['atomic.conf']), 'r')

    def tearDown(self):
        """
        Close the config file after every test.
        """
        self.conf.close()

    def test_config_file_is_valid_yaml(self):
        """
        Verifies atomic.conf is valid YAML.
        """
        self.assertEquals(type(yaml.safe_load(self.conf)), dict)

    def test_config_file_is_valid_yaml_with_items_uncommented(self):
        """
        Verifies atomic.conf is valid YAML when examples are uncommented.
        """
        # If a command line has a space after it, it's a comment
        # If a comment line has no space after it, it's an example
        uncommented = []
        for line in self.conf.readlines():
            if line.startswith('#') and len(line) > 2 and line[1] != ' ':
                line = line[1:]
            uncommented.append(line)
        self.assertEquals(type(yaml.safe_load('\n'.join(uncommented))), dict)


if __name__ == '__main__':
    unittest.main()
