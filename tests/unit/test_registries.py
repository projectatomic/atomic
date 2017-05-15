#pylint: skip-file

import unittest
from Atomic.util import is_backend_available, load_registries_from_yaml, get_registries
import json
import subprocess

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


@unittest.skipIf(no_mock, "Mock not found")
class TestRegistriesFromYAML(unittest.TestCase):

    def compare_list_of_dicts(self, results, answer):
        if not isinstance(results, list) or not isinstance(answer, list):
            raise AssertionError("Results must always be of type list")
        if len(results) != len(answer):
            raise AssertionError("Length of the lists differ.")
        for registry in results:
            self.assertDictEqual(registry, next(item for item in answer if item["hostname"] == registry['hostname']))

    def test_no_registries(self):
        with patch('Atomic.util.registries_tool_path') as reg_path:
            reg_path.return_value = "/usr/libexec/registries"
            with patch('Atomic.util.load_registries_from_yaml') as mockobj:
                mockobj.return_value = json.loads("{}")
                results = get_registries()
        answer = [{'name': 'docker.io', 'hostname': 'registry-1.docker.io', 'search': True, 'secure': True}]
        self.compare_list_of_dicts(results, answer)

    def test_block_dockerio(self):
        with patch('Atomic.util.registries_tool_path') as reg_path:
            reg_path.return_value = "/usr/libexec/registries"
            with patch('Atomic.util.load_registries_from_yaml') as mockobj:
                mockobj.return_value = json.loads('{"block_registries": ["docker.io"]}')
                results = get_registries()
        answer = []
        self.compare_list_of_dicts(results, answer)


    def test_duplicate_dockerio(self):
        with patch('Atomic.util.registries_tool_path') as reg_path:
            reg_path.return_value = "/usr/libexec/registries"
            with patch('Atomic.util.load_registries_from_yaml') as mockobj:
                mockobj.return_value = json.loads('{"registries": ["docker.io"]}')
                results = get_registries()
        answer = [{'secure': True, 'hostname': 'docker.io', 'name': 'docker.io', 'search': True}]
        self.compare_list_of_dicts(results, answer)

    def test_all(self):
        with patch('Atomic.util.registries_tool_path') as reg_path:
            reg_path.return_value = "/usr/libexec/registries"
            with patch('Atomic.util.load_registries_from_yaml') as mockobj:
                mockobj.return_value = json.loads('{"registries": ["one.com", "two.com"], "insecure_registries": ["three.com"], "block_registries": []}')
                results = get_registries()
        answer = [{'secure': True, 'search': True, 'name': 'one.com', 'hostname': 'one.com'}, {'secure': True, 'search': True, 'name': 'two.com', 'hostname': 'two.com'}, {'secure': True, 'search': True, 'name': 'three.com', 'hostname': 'three.com'}, {'secure': True, 'search': True, 'name': 'docker.io', 'hostname': 'registry-1.docker.io'}]
        self.compare_list_of_dicts(results, answer)

    def test_duplicate_in_secure_and_insecure(self):
        with patch('Atomic.util.registries_tool_path') as reg_path:
            reg_path.return_value = "/usr/libexec/registries"
            with patch('Atomic.util.load_registries_from_yaml') as mockobj:
                mockobj.return_value = json.loads('{"registries": ["one.com", "two.com"], "insecure_registries": ["two.com"], "block_registries": []}')
                self.assertRaises(ValueError, get_registries)

    def test_duplicate_in_registries(self):
        with patch('Atomic.util.registries_tool_path') as reg_path:
            reg_path.return_value = "/usr/libexec/registries"
            with patch('Atomic.util.load_registries_from_yaml') as mockobj:
                mockobj.return_value = json.loads('{"registries": ["one.com", "two.com", "one.com"], "insecure_registries": ["three.com"], "block_registries": []}')
                results = get_registries()
        answer = [{'secure': True, 'search': True, 'name': 'one.com', 'hostname': 'one.com'}, {'secure': True, 'search': True, 'name': 'two.com', 'hostname': 'two.com'}, {'secure': True, 'search': True, 'name': 'three.com', 'hostname': 'three.com'}, {'secure': True, 'search': True, 'name': 'docker.io', 'hostname': 'registry-1.docker.io'}]
        self.compare_list_of_dicts(results, answer)

if __name__ == '__main__':
    unittest.main()
