#!/usr/bin/python -Es

import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GObject, GLib
import slip.dbus.service
from slip.dbus import polkit
import os
import Atomic


class atomic_dbus(slip.dbus.service.Object):
    default_polkit_auth_required = "org.atomic.readwrite"

    class Args():
        def __init__(self, image):
            self.image = image
            self.recurse = False

    def __init__(self, *p, **k):
        super(atomic_dbus, self).__init__(*p, **k)
        self.atomic = Atomic.Atomic()

    """
    The version method takes in an image name and returns its version
    information
    """
    @slip.dbus.polkit.require_auth("org.atomic.read")
    @dbus.service.method("org.atomic", in_signature='asb',
                         out_signature='aa{sv}')
    def version(self, images, recurse=False):
        versions = []
        for image in images:
            args = self.Args(str(image))
            args.recurse = recurse
            self.atomic.set_args(args)
            versions.append({"Image": image,
                             "Version": self.atomic.version()})
        return versions

    """
    The verify method takes in an image name and returns whether or not the
    image should be updated
    """
    @slip.dbus.polkit.require_auth("org.atomic.read")
    @dbus.service.method("org.atomic", in_signature='as', out_signature='av')
    def verify(self, images):
        verifications = []
        for image in images:
            args = self.Args(str(image))
            self.atomic.set_args(args)
            verifications.append({"Image": image,
                                  "Verification": self.atomic.verify()})
        return verifications


if __name__ == "__main__":
        mainloop = GLib.MainLoop()
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        system_bus = dbus.SystemBus()
        name = dbus.service.BusName("org.atomic", system_bus)
        object = atomic_dbus(system_bus, "/org/atomic/object")
        slip.dbus.service.set_mainloop(mainloop)
        mainloop.run()
