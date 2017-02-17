#!/usr/bin/env python
#pylint: skip-file

import dbus
import sys
try:
    from slip.dbus import polkit
except ImportError:
    sys.exit(77)
import dbus.service
import dbus.mainloop.glib


# Throw this error to signify at test failure
class AtomicIntegrationTestError(Exception):
    def __init__(self, test_name):
        super(AtomicIntegrationTestError, self).__init__("Test '{}' Failed...".format(test_name))


# Wrapper class for the decorator
def integration_test(func):
    def _integration_test(self):
        return func(self)
    return _integration_test


class TestDBus():

    def __init__(self):
        self.bus = dbus.SystemBus()
        self.dbus_object = self.bus.get_object("org.atomic", "/org/atomic/object")

    # Add this decorator to define the method as something that should be
    # tested
    @integration_test
    @polkit.enable_proxy
    def test_scan_list(self):
        results = self.dbus_object.ScanList()
        assert(isinstance(results, dbus.String))



if __name__ == '__main__':

    def get_test_methods(_tb):
        """
        Returns the test methods from above that have the integration_test decorator
        :param _tb: TestDbus instance
        """

        test_method_names = [x for x in dir(_tb) if not x.startswith('__')]
        test_methods = []
        for method in test_method_names:
            _method = getattr(_tb, method)
            if callable(_method) and _method.__getattribute__('__name__') == '_integration_test':
                test_methods.append(method)
        return test_methods

    tb = TestDBus()
    test_methods = get_test_methods(tb)

    for test in reversed(test_methods):
        _tb = getattr(tb, test)
        try:
            _tb()
        except:
            raise AtomicIntegrationTestError(test)

        print("Test '{}' passed.".format(test))

