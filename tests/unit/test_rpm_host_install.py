#pylint: skip-file
import os
import shutil
import tempfile
import unittest
import json
from Atomic.rpm_host_install import RPMHostInstall


no_mock = True
try:
    from unittest.mock import ANY, patch, call
    no_mock = False
except ImportError:
    try:
        from mock import ANY, patch, call
        no_mock = False
    except ImportError:
        # Mock is already set to False
        pass

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

@unittest.skipIf(no_mock, "Mock not found")
class TestRPMHostInstall(unittest.TestCase):

    @patch("Atomic.rpm_host_install.RPMHostInstall.file_checksum")
    def test_rm_add_files_to_host(self, _fc):
        """
        This function tests the following 3 functionalities:
        1: When old_installed_files_checksum do exist, test if the files will be removed
        2: When file is in the specified 'tempalte', check to see if its content get swapped
        3: When file not in the template, files should be copied instead

        Also Note, the function skips checking for the return value, as I felt the 'external effect' is what matters
        in this test
        """

        _fc.return_value = "15"
        def check_file_removal(tmpdir):
            # Test for the first case
            test_old_installed_file = tempfile.mkstemp(prefix=tmpdir)
            test_old_installed_file_path = test_old_installed_file[1]
            changed_file_dict = {test_old_installed_file_path : "0"}
            non_changed_file_dict = {test_old_installed_file_path : "15"}

            RPMHostInstall.rm_add_files_to_host(changed_file_dict, None)
            self.assertTrue(os.path.exists(test_old_installed_file_path))
            RPMHostInstall.rm_add_files_to_host(non_changed_file_dict, None)
            self.assertFalse(os.path.exists(test_old_installed_file_path))

        def setup_and_collect_export_hostfs_files(tmpdir):
            exports_hostfs_dir = os.path.join(tmpdir, "hostfs")
            exports_hostfs_tempdir = exports_hostfs_dir +  tmpdir
            os.makedirs(exports_hostfs_tempdir)
            # Note about the location here, as we have to make files start with /exports/hostfs
            # and we want to use the benefit from tmpdir, we have to have the format of /exports/hostfs/tmpdir
            exports_hostfs_file = os.path.join(exports_hostfs_tempdir, "test.file")

            return exports_hostfs_file, exports_hostfs_dir

        def get_real_exports_file_path(exports_hostfs_file, exports_hostfs_dir):
            # Find the relative path of the file to exports/hostfs (which is actually the true path under '/' in this contenxt)
            rel_file_path = os.path.relpath(exports_hostfs_file, exports_hostfs_dir)
            real_file_path = os.path.join("/", rel_file_path)
            template_set = [real_file_path]
            return template_set

        def write_exports_file(exports_hostfs_file):
            # When the files are already set up, we begin calling function
            content = {"test_one" : "$test_swap"}
            with open(exports_hostfs_file, 'w') as json_file:
                json_file.write(json.dumps(content, indent=4))
                json_file.write("\n")

        def prepare_test_case(tmpdir):
            exports_host_file, exports_hostfs_dir = setup_and_collect_export_hostfs_files(tmpdir)
            template_set = get_real_exports_file_path(exports_host_file, exports_hostfs_dir)
            write_exports_file(exports_host_file)
            values = {"test_swap" : "test_result"}

            return template_set, values

        def check_value_swap(template_set, values, tmpdir):
            real_file_path = template_set[0]
            RPMHostInstall.rm_add_files_to_host(None, tmpdir, files_template=template_set, values=values)
            self.assertTrue(os.path.exists(real_file_path))
            with open(real_file_path, "r") as f:
                json_val = json.loads(f.read())
            self.assertEqual(json_val["test_one"], "test_result")

            # Do the cleanup and check last case
            os.remove(real_file_path)

        try:
            tmpdir = tempfile.mkdtemp()

            # Test for the first case
            check_file_removal(tmpdir)

            # Test for the second case
            template_set, values = prepare_test_case(tmpdir)
            check_value_swap(template_set, values, tmpdir)

            # Test for the third case
            real_file_path = template_set[0]
            RPMHostInstall.rm_add_files_to_host(None, tmpdir)
            self.assertTrue(os.path.exists(real_file_path))

        finally:
            shutil.rmtree(tmpdir)

if __name__ == '__main__':
    unittest.main()
