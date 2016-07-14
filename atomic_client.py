import sys
import json
import dbus
import time
import dbus.service
import dbus.mainloop.glib
from Atomic import util
from slip.dbus import polkit


class AtomicDBus (object):
    def __init__(self):
        self.bus = dbus.SystemBus()
        self.dbus_object = self.bus.get_object("org.atomic", "/org/atomic/object")

    @polkit.enable_proxy
    def version(self, image, recurse):
        ret = self.dbus_object.Version(image, recurse, dbus_interface="org.atomic")
        return ret

    @polkit.enable_proxy
    def verify(self, image):
        ret = self.dbus_object.Verify(image, dbus_interface="org.atomic")
        return ret

    @polkit.enable_proxy
    def storage_reset(self):
        self.dbus_object.StorageReset(dbus_interface="org.atomic")

    @polkit.enable_proxy
    def storage_import(self, graph, import_location):
        self.dbus_object.StorageImport(graph, import_location, dbus_interface="org.atomic")

    @polkit.enable_proxy
    def storage_export(self, graph, export_location, force):
        self.dbus_object.StorageExport(graph, export_location, force, dbus_interface="org.atomic")

    @polkit.enable_proxy
    def storage_modify(self, devices, driver):
        self.dbus_object.StorageModify(devices, driver, dbus_interface="org.atomic")

    @polkit.enable_proxy
    def diff(self, first, second):
        ret = self.dbus_object.Diff(first, second, dbus_interface="org.atomic", timeout = 2147400)
        return ret

    @polkit.enable_proxy
    def scan_list(self):
        ret = self.dbus_object.ScanList(dbus_interface="org.atomic")
        return ret

    @polkit.enable_proxy
    def async_scan(self, scan_targets, scanner, scan_type, rootfs, _all, images, containers):
        token = self.dbus_object.ScheduleScan(scan_targets, scanner, scan_type, rootfs, _all, images, containers, dbus_interface="org.atomic", timeout = 2147400)
        while(True):
            ret = self.dbus_object.GetScanResults(token, dbus_interface="org.atomic")
            if ret:
                break
            time.sleep(1)

        return ret

    @polkit.enable_proxy
    def scan(self, scan_targets, scanner, scan_type, rootfs, _all, images, containers):
        ret = self.dbus_object.Scan(scan_targets, scanner, scan_type, rootfs, _all, images, containers, dbus_interface="org.atomic", timeout = 2147400)
        return ret

#For outputting the list of scanners
def print_scan_list(all_scanners):
    if len(all_scanners) == 0:
        util.write_out("There are no scanners configured for this system.")
        sys.exit(0)
    default_scanner = (util.get_atomic_config())['default_scanner']
    if default_scanner is None:
        default_scanner = ''
    for scanner in all_scanners:
        scanner_name = scanner['scanner_name']
        df = '* ' if scanner_name == default_scanner else ''
        default_scan_type = scanner.get('default_scan')
        if default_scan_type is None:
            raise ValueError("Invalid configuration file: At least one scan type must be "
                                 "declared as the default for {}.".format(scanner_name))
        util.write_out("Scanner: {} {}".format(scanner_name, df))
        util.write_out("{}Image Name: {}".format(" " * 2, scanner['image_name']))
        for scan_type in scanner['scans']:
            df = '* ' if default_scan_type == scan_type['name'] else ''
            util.write_out("{}Scan type: {} {}".format(" " * 5, scan_type['name'], df))
            util.write_out("{}Description: {}\n".format(" " * 5, scan_type['description']))
        util.write_out("\n* denotes defaults")
        sys.exit(0)

if __name__ == "__main__":
    try:
        dbus_proxy = AtomicDBus()
        if(sys.argv[1] == "version"):
            if sys.argv[2] == "-r":
                resp = dbus_proxy.version(sys.argv[3:], True)
            else:
                resp = dbus_proxy.version(sys.argv[2:], False)

            for r in resp:
                for v in r["Version"]:
                    print(str(v["Id"]), str(v["Version"]), str(v["Tag"]))

        elif(sys.argv[1] == "verify"):
            resp = dbus_proxy.verify(sys.argv[2:])
            for r in resp:
                print(r)

        elif(sys.argv[1] == "storage"):
            #handles atomic storage export
            if(sys.argv[2] == "export"):
                dbus_proxy.storage_export("/var/lib/Docker", "/var/lib/atomic/migrate", False)

            #handles atomic storage import
            elif(sys.argv[2] == "import"):
                dbus_proxy.storage_import("/var/lib/Docker", "/var/lib/atomic/migrate")

            #handles atomic storage reset
            elif(sys.argv[2] == "reset"):
                dbus_proxy.storage_reset()

        elif(sys.argv[1] == "diff"):
            #case where rpms flag is passed in
            resp = json.loads(dbus_proxy.diff(sys.argv[2], sys.argv[3]))
            print(resp)

        elif(sys.argv[1] == "scan"):
            if(sys.argv[2] == "--list"):
                print_scan_list(json.loads(dbus_proxy.scan_list()))

            elif(sys.argv[2] == "--all"):
                print (json.loads(dbus_proxy.scan([], '', '', [], True, False, False)))

            elif(sys.argv[2] == "--images"):
                print (json.loads(dbus_proxy.scan([], '', '', [], False, True, False)))

            elif(sys.argv[2] == "--containers"):
                print (json.loads(dbus_proxy.scan([], '', '', [], False, False, True)))

            else:
                print (json.loads(dbus_proxy.scan([sys.argv[2]], '', '', [], False, False, False)))
    except dbus.DBusException as e:
        print (e)
