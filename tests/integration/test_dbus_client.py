#!/usr/bin/env python
#pylint: skip-file
run_test = True

try:
    from atomic_dbus_client import AtomicDBus
except ImportError:
    run_test = False
import sys
import subprocess
import tempfile

_integration_test_serial = 0

clean_up_tasks = []

# Throw this error to signify at test failure
class AtomicIntegrationTestError(Exception):
    def __init__(self, test_name, error):
        super(AtomicIntegrationTestError, self).__init__("Test '{}' Failed... due to {}".format(test_name, error))


def integration_test(func):
    global _integration_test_serial
    func._integration_test_serial = _integration_test_serial
    _integration_test_serial += 1
    return func

def skip_integration_test(func):
    func._skip = True
    return func

class TestDBus():

    def __init__(self):
        self.dbus_client = AtomicDBus()
        self.cid = None
        self.registry_cid = None

    @staticmethod
    def run_cmd(cmd):
        if not isinstance(cmd, list):
            cmd = cmd.split()
        return subprocess.check_output(cmd)

    @staticmethod
    def add_cleanup_cmd(cmd):
        assert(isinstance(cmd, str))
        clean_up_tasks.append(cmd.split())

    @staticmethod
    def remove_cleanup_cmd(cmd):
        assert(isinstance(cmd, str))
        clean_up_tasks.remove(cmd.split())

    @staticmethod
    def cleanup():
        for task in clean_up_tasks:
            print("Running clean up: {}".format(" ".join(task)))
            TestDBus.run_cmd(task)


    # Add this decorator to define the method as something that should be
    # tested

    @integration_test
    def test_ContainersList(self):
        self.dbus_client.ContainersList()

    @integration_test
    def test_DeleteContainer(self):
        TestDBus.add_cleanup_cmd('docker rmi docker.io/library/busybox:1.24')
        self.run_cmd(['docker', 'pull', 'docker.io/library/busybox:1.24'])
        self.run_cmd(['docker', 'run', 'docker.io/library/busybox:1.24', 'ls'])
        bb_cid = TestDBus.run_cmd('docker ps -aq -l').decode('utf-8').rstrip()
        self.dbus_client.ContainersDelete(bb_cid)

    @skip_integration_test
    @integration_test
    def test_Containers_Trim(self):
        # Not quite sure how to test this accurately and consistently
        pass

    @integration_test
    def test_Diff(self):
        self.dbus_client.Diff('atomic-test-1', 'atomic-test-3', rpms=True)

    @integration_test
    def test_Stop(self):
        self.run_cmd(['docker', 'pull', 'docker.io/library/busybox:1.24'])
        self.run_cmd(['docker', 'run', '-d', 'docker.io/library/busybox:1.24', 'sleep', '1000'])
        bb_cid = TestDBus.run_cmd('docker ps -aq -l').decode('utf-8').rstrip()
        self.dbus_client.Stop(bb_cid)
        TestDBus.add_cleanup_cmd('docker rm {}'.format(bb_cid))
        TestDBus.add_cleanup_cmd('docker rmi -f docker.io/library/busybox:1.24')

    @skip_integration_test
    @integration_test
    def test_StorageExport(self):
        pass

    @skip_integration_test
    @integration_test
    def test_StorageImport(self):
        pass

    @skip_integration_test
    @integration_test
    def test_StorageModify(self):
        pass

    @skip_integration_test
    @integration_test
    def test_StorageReset(self):
        pass

    @skip_integration_test
    @integration_test
    def test_AsyncScan(self):
        pass

    @integration_test
    def test_ImagesDelete(self):
        self.run_cmd(['docker', 'pull', 'docker.io/projectatomic/atomic-tester:latest'])
        self.run_cmd(['docker', 'tag', 'docker.io/projectatomic/atomic-tester:latest', 'dbus_client_foobar'])
        self.dbus_client.ImagesDelete('dbus_client_foobar')

    @integration_test
    def test_ImagesTag(self):
        self.run_cmd(['docker', 'pull', 'docker.io/projectatomic/atomic-tester:latest'])
        self.dbus_client.ImagesTag('docker.io/projectatomic/atomic-tester:latest', 'dbus_client_foobar')
        TestDBus.add_cleanup_cmd('docker rmi dbus_client_foobar')

    @skip_integration_test
    @integration_test
    def test_ImagesHelp(self):
        self.dbus_client.ImagesHelp('atomic-test-3')

    @integration_test
    def test_ImagesInfo(self):
        self.dbus_client.ImagesInfo('atomic-test-3')
        self.dbus_client.ImagesInfo('docker.io/projectatomic/atomic-tester:latest', remote=True)

    @integration_test
    def test_ImagesList(self):
        self.dbus_client.ImagesList()

    @integration_test
    def test_ImagesPrune(self):
        self.dbus_client.ImagesPrune()

    @integration_test
    def test_ImagePull(self):
        self.dbus_client.ImagePull('docker.io/library/busybox:1.24')
        TestDBus.add_cleanup_cmd('docker rmi -f docker.io/library/busybox:1.24')
        self.dbus_client.ImagePull('docker.io/library/busybox:1.24', storage='ostree')
        self.dbus_client.ImagesDelete('docker.io/library/busybox:1.24', storage='ostree')

    @integration_test
    def test_ImageUpdate(self):
        self.dbus_client.ImagePull('docker.io/library/busybox:1.24')
        self.run_cmd(['docker', 'tag', 'docker.io/library/busybox:1.24', 'docker.io/library/busybox:latest'])
        self.run_cmd(['docker', 'rmi', 'docker.io/library/busybox:1.24'])
        TestDBus.add_cleanup_cmd('docker rmi -f docker.io/library/busybox:latest')
        self.dbus_client.ImageUpdate('docker.io/library/busybox:latest')

    @integration_test
    def test_ImageVersion(self):
        self.dbus_client.ImageVersion('atomic-test-3')
    
    @integration_test
    def test_install(self):
        self.dbus_client.Install('atomic-test-3')
        cid = TestDBus.run_cmd('docker ps -aq -l').decode('utf-8').rstrip()
        TestDBus.add_cleanup_cmd('docker rm -f {}'.format(cid))
        self.run_cmd(['docker', 'save', '-o', '/tmp/atomic-test-system.tmp', 'atomic-test-system'])
        self.dbus_client.ImagePull('dockertar://tmp/atomic-test-system.tmp', storage='ostree')
        self.dbus_client.Install('atomic-test-system', name='atomic-test-system', system=True, storage='ostree')
        self.run_cmd(['rm', '-f', '/tmp/atomic-test-system.tmp'])
        self.dbus_client.ContainersDelete('atomic-test-system', storage='ostree')
        self.dbus_client.ImagesDelete('atomic-test-system', storage='ostree')
    
    @integration_test
    def test_MountImage(self):
        mnt_dir = tempfile.mkdtemp()
        self.dbus_client.MountImage('atomic-test-3', mnt_dir)
        self.dbus_client.UnmountImage(mnt_dir)
        TestDBus.add_cleanup_cmd('rmdir {}'.format(mnt_dir))

    @integration_test
    def test_Run(self):
        self.dbus_client.Run('atomic-test-3')
        cid = TestDBus.run_cmd('docker ps -aq -l').decode('utf-8').rstrip()
        TestDBus.add_cleanup_cmd('docker rm -f {}'.format(cid))

    @skip_integration_test
    @integration_test
    def test_Scan(self):
        pass

    @integration_test
    def test_ScanList(self):
        self.dbus_client.ScanList()

    @skip_integration_test
    @integration_test
    def test_Sign(self):
        pass

    @integration_test
    def test_Top(self):
        self.dbus_client.Top()

    @skip_integration_test
    @integration_test
    def test_TrustAdd(self):
        pass

    @skip_integration_test
    @integration_test
    def test_TrustDefaultPolicy(self):
        pass

    @skip_integration_test
    @integration_test
    def test_TrustDelete(self):
        pass

    @skip_integration_test
    @integration_test
    def test_TrustShow(self):
        pass

    @integration_test
    def test_Uninstall(self):
        self.run_cmd(['docker', 'tag', 'atomic-test-3', 'dbus-test-uninstall'])
        self.dbus_client.Install('dbus-test-uninstall')
        self.dbus_client.Uninstall('dbus-test-uninstall', force=True)

    @skip_integration_test
    @integration_test
    def test_UnmountImage(self):
        # unmount is already tested in test_Mount
        pass


    @integration_test
    def test_Verify(self):
        TestDBus.add_cleanup_cmd('docker rmi docker.io/library/busybox:latest')
        self.run_cmd(['docker', 'pull', 'docker.io/library/busybox:1.24'])
        self.run_cmd(['docker', 'tag', 'docker.io/library/busybox:1.24', 'docker.io/library/busybox:latest'])
        self.run_cmd(['docker', 'rmi', 'docker.io/library/busybox:1.24'])
        self.dbus_client.Verify('docker.io/library/busybox:latest')

    @integration_test
    def test_vulnerable(self):
        self.dbus_client.vulnerable()

    @skip_integration_test
    @integration_test
    def test_GetScanResultsById(self):
        pass


if __name__ == '__main__':
    if not run_test:
        print("Skipping due to lack of dbus slip module")
        sys.exit(0)

    def get_test_methods(_tb):
        """
        Returns the test methods from above that have the integration_test decorator
        :param _tb: TestDbus instance
        """
        method_names = (n for n in dir(_tb) if not n.startswith('__') and
                        callable(getattr(_tb, n)))
        methods_and_names = ((getattr(_tb, n), n) for n in method_names)

        test_method_names_order = (
            (x[1], getattr(x[0], '_integration_test_serial'))
            for x in methods_and_names
            if '_integration_test_serial' in dir(x[0]))
        test_method_names_ordered = [x[0] for x in
                                     sorted(test_method_names_order,
                                            key=lambda x: x[1])]

        return test_method_names_ordered

    def get_skip_methods(_tb):
        method_names = (n for n in dir(_tb) if not n.startswith('__') and
                        callable(getattr(_tb, n)))
        methods_and_names = ((getattr(_tb, n), n) for n in method_names)
        skip_methods = []
        for x in methods_and_names:
            if '_integration_test_serial' in dir(x[0]) and '_skip' in dir(x[0]):
                skip_methods.append(x[1])
        return skip_methods


    tb = TestDBus()
    test_methods = get_test_methods(tb)
    skip_methods = get_skip_methods(tb)
    for test in test_methods:
        if test not in skip_methods:
            _tb = getattr(tb, test)
            try:
                _tb()
                print("Test '{}' passed.".format(test))
            except ValueError as e:
                print("Test '{}' failed.".format(test))
                raise AtomicIntegrationTestError(test, e)
            finally:
                tb.cleanup()
                clean_up_tasks = []
        else:
            print("Test '{}' skipped.".format(test))


