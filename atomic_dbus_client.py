#! /usr/bin/python3 -Es
import sys
import dbus
import time
from Atomic import util
from slip.dbus import polkit
import dbus.service
import dbus.mainloop.glib

class AtomicDBus (object):
    def __init__(self):
        self.bus = dbus.SystemBus()
        self.dbus_object = self.bus.get_object("org.atomic", "/org/atomic/object")

    @polkit.enable_proxy
    def ContainersList(self):
        return self.dbus_object.ContainersList(dbus_interface="org.atomic")

    @polkit.enable_proxy
    def ContainersDelete(self, containers, containers_all=False, force=False):
        if not isinstance(containers, (list, tuple)):
            containers = [ containers ]
        return self.dbus_object.ContainersDelete(containers, containers_all, force, dbus_interface="org.atomic")

    @polkit.enable_proxy
    def ContainersTrim(self):
        return self.dbus_object.ContainersTrim(dbus_interface="org.atomic", timeout = 2147400)

    @polkit.enable_proxy
    def Diff(self, first, second, rpms=False, no_files=False, names_only=False):
        return self.dbus_object.Diff(first, second, rpms, no_files, names_only, dbus_interface="org.atomic", timeout = 2147400)

    @polkit.enable_proxy
    def Stop(self, image, name=None, extra_args=None):
        if not name:
            name = image
        if not extra_args:
            extra_args = []
        if not isinstance(extra_args, (list, tuple)):
            extra_args = [ extra_args ]
        return self.dbus_object.Install(image, name, extra_args, dbus_interface="org.atomic", timeout = 2147400)

    @polkit.enable_proxy
    def StorageExport(self, graph, export_location, force):
        self.dbus_object.StorageExport(graph, export_location, force, dbus_interface="org.atomic")

    @polkit.enable_proxy
    def StorageImport(self, graph, import_location):
        self.dbus_object.StorageImport(graph, import_location, dbus_interface="org.atomic")

    @polkit.enable_proxy
    def StorageModify(self, devices, driver):
        self.dbus_object.StorageModify(devices, driver, dbus_interface="org.atomic")

    @polkit.enable_proxy
    def StorageReset(self):
        self.dbus_object.StorageReset(dbus_interface="org.atomic")

    @polkit.enable_proxy
    def AsyncScan(self, scan_targets, scanner, scan_type, rootfs, _all, images, containers):
        token = self.dbus_object.ScheduleScan(scan_targets, scanner, scan_type, rootfs, _all, images, containers, dbus_interface="org.atomic", timeout = 2147400)
        while(True):
            ret = self.dbus_object.GetScanResults(token, dbus_interface="org.atomic")
            if ret:
                break
            time.sleep(1)

        return ret

    @polkit.enable_proxy
    def ImagesDelete(self, images, force=False, remote=False):
        if not isinstance(images, (list, tuple)):
            images = [ images ]
        return self.dbus_object.ImagesDelete(images, remote, force, dbus_interface="org.atomic")

    @polkit.enable_proxy
    def ImagesHelp(self, image):
        return self.dbus_object.ImagesHelp(image, dbus_interface="org.atomic")

    @polkit.enable_proxy
    def ImagesInfo(self, image, remote=False):
        return self.dbus_object.ImagesInfo(image, remote, dbus_interface="org.atomic")

    @polkit.enable_proxy
    def ImagesList(self):
        return self.dbus_object.ImagesList(dbus_interface="org.atomic")

    @polkit.enable_proxy
    def ImagesPrune(self):
        return self.dbus_object.ImagesPrune(dbus_interface="org.atomic")

    # The ImagesPull method will pull the specified image
    @polkit.enable_proxy
    def ImagePull(self, image, storage="docker", reg_type=""):
        return self.dbus_object.ImagePull(image, storage, reg_type, dbus_interface="org.atomic", timeout = 2147400)

    def ImagesUpdate(self, images, force=False):
        if not isinstance(images, (list, tuple)):
            images = [ images ]
        return self.dbus_object.ImagesInfo(images, force, dbus_interface="org.atomic")

    @polkit.enable_proxy
    def ImageVersion(self, image, recurse=False):
        return self.dbus_object.ImageVersion(image, recurse, dbus_interface="org.atomic")

    @polkit.enable_proxy
    def Install(self, image, name=None, user=False, system=False, remote="", setvalues=None, extra_args=None):
        if not name:
            name = image
        if not setvalues:
            setvalues = []
        if not isinstance(setvalues, (list, tuple)):
            setvalues = [ setvalues ]
        if not extra_args:
            extra_args = []
        if not isinstance(extra_args, (list, tuple)):
            extra_args = [ extra_args ]
        return self.dbus_object.Install(image, name, user, system, remote, setvalues, extra_args, dbus_interface="org.atomic", timeout = 2147400)

    @polkit.enable_proxy
    def MountImage(self, src, dest, options="", live=False, shared=False):
        ret = self.dbus_object.MountImage(src, dest, options, live, shared, dbus_interface="org.atomic")
        return ret

    # The Run method will create and run a container on the specified image
    @polkit.enable_proxy
    def Run(self, image, name=None, spc=False, detach=False, command=None):
        if not name:
            name = image
        if not command:
            command = []
        if not isinstance(command, (list, tuple)):
            command = [ command ]
        return self.dbus_object.Run(image, name, spc, detach, command, dbus_interface="org.atomic", timeout = 2147400)

    @polkit.enable_proxy
    def Scan(self, scan_targets, scanner, scan_type, rootfs, _all, images, containers):
        return self.dbus_object.Scan(scan_targets, scanner, scan_type, rootfs, _all, images, containers, dbus_interface="org.atomic", timeout = 2147400)

    @polkit.enable_proxy
    def ScanList(self):
        ret = self.dbus_object.ScanList(dbus_interface="org.atomic")
        return ret

    @polkit.enable_proxy
    def Sign(self, images, sign_by, signature_path = "", gnupghome=""):
        if not isinstance(images, (list, tuple)):
            images = [ images ]
        return self.dbus_object.Sign(images, sign_by, signature_path, gnupghome, dbus_interface="org.atomic")

    @polkit.enable_proxy
    def Top(self, containers=None, options=""):
        if not containers:
            containers=[]
        if not isinstance(containers, (list, tuple)):
            containers = [ containers ]
        return self.dbus_object.Top(containers, options, dbus_interface="org.atomic")

    @polkit.enable_proxy
    def TrustAdd(self, registry, trusttype="reject", pubkeys="", keytype="GPGKeys", sigstore="", sigstoretype="web"):
        return self.dbus_object.TrustAdd(registry, trusttype, pubkeys, keytype, sigstore, sigstoretype, dbus_interface="org.atomic")

    @polkit.enable_proxy
    def TrustDefaultPolicy(self, policy):
        return self.dbus_object.TrustDefaultPolicy(policy, dbus_interface="org.atomic")

    @polkit.enable_proxy
    def TrustDelete(self, registry, trusttype="None"):
        return self.dbus_object.TrustDelete(registry, trusttype, dbus_interface="org.atomic")

    @polkit.enable_proxy
    def TrustShow(self):
        return self.dbus_object.TrustShow(dbus_interface="org.atomic")

    @polkit.enable_proxy
    def Uninstall(self, image, name=None, force=False, extra_args=None):
        if not name:
            name = image
        if not extra_args:
            extra_args = []
        if not isinstance(extra_args, (list, tuple)):
            extra_args = [ extra_args ]
        return self.dbus_object.Install(image, name, force, extra_args, dbus_interface="org.atomic", timeout = 2147400)

    @polkit.enable_proxy
    def UnmountImage(self, dest):
        ret = self.dbus_object.UnmountImage(dest, dbus_interface="org.atomic")
        return ret

    @polkit.enable_proxy
    def Verify(self, image):
        ret = self.dbus_object.Verify(image, dbus_interface="org.atomic")
        return ret

    @polkit.enable_proxy
    def vulnerable(self):
        return self.dbus_object.VulnerableInfo(dbus_interface="org.atomic")

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

def is_number(var):
    try:
        int(var)
        return True
    except ValueError:
        return False

def convert_str(val):
    if val in ("True", "False"):
        return val
    if is_number(val):
        return val
    if val[0] == "[":
        return val
    return "\"%s\"" % val

if __name__ == "__main__":
    dbus_proxy = AtomicDBus()
    cmd="dbus_proxy.%s(" % sys.argv[1]

    if len(sys.argv[2:]) > 0:
        cmd+=convert_str(sys.argv[2])

    for i in sys.argv[3:]:
        cmd+=","
        cmd+=convert_str(i)
    cmd+=")"
    print(cmd)
    try:
        s = eval(cmd) # pylint: disable=eval-used
        if s:
            print(s)
    except dbus.exceptions.DBusException as e:
        print(e.get_dbus_message())
        sys.exit(-1)
