import sys

import dbus
import dbus.service
import dbus.mainloop.glib
from slip.dbus import polkit


class AtomicDBus (object):
    def __init__(self):
        self.bus = dbus.SystemBus()
        self.dbus_object = self.bus.get_object("org.atomic", "/org/atomic/object")

    @polkit.enable_proxy
    def version(self, image, recurse):
        ret = self.dbus_object.version(image, recurse, dbus_interface="org.atomic")
        return ret

    @polkit.enable_proxy
    def verify(self, image):
        ret = self.dbus_object.verify(image, dbus_interface="org.atomic")
        return ret

    @polkit.enable_proxy
    def storage_reset(self):
        self.dbus_object.storage_reset(dbus_interface="org.atomic")

    @polkit.enable_proxy
    def storage_import(self, graph, import_location):
        self.dbus_object.storage_import(graph, import_location, dbus_interface="org.atomic")

    @polkit.enable_proxy
    def storage_export(self, graph, export_location, force):
        self.dbus_object.storage_export(graph, export_location, force, dbus_interface="org.atomic")

    @polkit.enable_proxy
    def storage_modify(self, devices, driver):
        self.dbus_object.storage_import(devices, driver, dbus_interface="org.atomic")

    @polkit.enable_proxy
    def diff(self, first, second):
        ret = self.dbus_object.diff(first, second, dbus_interface="org.atomic")
        return ret


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
                print r

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
            resp = dbus_proxy.diff(sys.argv[2], sys.argv[3])
            print str(resp)
    except dbus.DBusException as e:
        print (e)
