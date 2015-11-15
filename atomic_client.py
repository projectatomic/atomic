import sys

import dbus
import dbus.service
import dbus.mainloop.glib
from slip.dbus import polkit


class AtomicDBus (object):
    def __init__(self):
        self.bus = dbus.SystemBus()
        self.dbus_object = self.bus.get_object("org.atomic",
                                               "/org/atomic/object")

    @polkit.enable_proxy
    def version(self, image, recurse):
        ret = self.dbus_object.version(image, recurse,
                                       dbus_interface="org.atomic")
        return ret

    @polkit.enable_proxy
    def verify(self, image):
        ret = self.dbus_object.verify(image, dbus_interface="org.atomic")
        return ret


if __name__ == "__main__":
    try:
        dbus_proxy = AtomicDBus()
        resp = dbus_proxy.version(sys.argv[1:], True)
        for r in resp:
            for v in r["Version"]:
                print(v["Id"], v["Version"], v["Tag"])
    except dbus.DBusException as e:
        print (e)
