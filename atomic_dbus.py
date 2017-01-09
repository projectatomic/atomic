#!/usr/bin/python -Es

import threading
import time

import dbus
import dbus.mainloop.glib
import json
from gi.repository import GObject
import slip.dbus.service
import Atomic
import dbus.service
from Atomic.containers import Containers
from Atomic.delete import Delete
from Atomic.diff import Diff
from Atomic.help import AtomicHelp
from Atomic.info import Info
from Atomic.install import Install
from Atomic.mount import Mount
from Atomic.images import Images
from Atomic.pull import Pull
from Atomic.run import Run
from Atomic.scan import Scan
from Atomic.sign import Sign
from Atomic.stop import Stop
from Atomic.storage import Storage
from Atomic.top import Top
from Atomic.trust import Trust
from Atomic.update import Update
from Atomic.uninstall import Uninstall
from Atomic.verify import Verify

DBUS_NAME_FLAG_DO_NOT_QUEUE = 4
DBUS_REQUEST_NAME_REPLY_PRIMARY_OWNER = 1

class atomic_dbus(slip.dbus.service.Object):
    default_polkit_auth_required = "org.atomic.readwrite"

    class Args():
        def __init__(self):
            self.all = False
            self.args = []
            self.assumeyes = True
            self.command = []
            self.compares = []
            self.container = False
            self.containers = []
            self.debug = False
            self.default_policy = None
            self.delete_targets = []
            self.devices = None
            self.diff = False
            self.display = False
            self.downgrade=False
            self.driver = None
            self.export_location = None
            self.force = False
            self.gnupghome = None
            self.graph = None
            self.heading = False
            self.hotfix = False
            self.image = None
            self.images = []
            self.import_location = None
            self.json = True
            self.keytype = None
            self.list = False
            self.live = False
            self.mountpoint = None
            self.name = None
            self.names_only = False
            self.no_files = False
            self.optional = None
            self.options = None
            self.os = None
            self.pretty = False
            self.preview = False
            self.prune = False
            self.pubkeys = []
            self.quiet = True
            self.raw = False
            self.rebase=False
            self.reboot=False
            self.reboot=False
            self.recurse = False
            self.refspec = None
            self.reg_type = None
            self.registry = None
            self.remote = False
            self.revision = None
            self.rootfs = []
            self.rpms = False
            self.save = False
            self.scan_targets = []
            self.scan_type = None
            self.scanner = None
            self.setvalues = []
            self.shared = False
            self.sign_by = None
            self.signature_path = None
            self.sigstore = None
            self.sigstoretype = None
            self.spc = False
            self.detach = False
            self.storage = None
            self.system = False
            self.truncate = False
            self.trust_type = None
            self.user = None
            self.verbose = False

    def __init__(self, *p, **k):
        super(atomic_dbus, self).__init__(*p, **k)
        self.atomic = Atomic.Atomic()
        self.tasks = []
        self.tasks_lock = threading.Lock()
        self.last_token = 0
        self.scheduler_thread = threading.Thread(target = self.Scheduler)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        self.results = dict()
        self.results_lock = threading.Lock()

    def Scheduler(self):
        while True:
            current_task = None
            with self.tasks_lock:
                if(len(self.tasks) > 0):
                    current_task = self.tasks.pop(0)
            if current_task is not None:
                result = current_task[1].scan()
                with self.results_lock:
                    self.results[current_task[0]] = result
            time.sleep(1)

    def AllocateToken(self):
        with self.tasks_lock:
            self.last_token += 1
            return self.last_token

    # atomic diff section
    # The Diff method shows differences between two container images, file
    # diff or RPMS.
    @slip.dbus.polkit.require_auth("org.atomic.read")
    @dbus.service.method("org.atomic", in_signature='ssbbb',out_signature='s')
    def Diff(self, src, dest, rpms, no_files, names_only):
        diff = Diff()
        args = self.Args()
        args.compares = [src, dest]
        args.verbose = True
        args.no_files = no_files
        args.names_only = names_only
        args.rpms = rpms
        diff.set_args(args)
        return json.dumps(diff.diff())

    # atomic containers section
    # The ContainersList method will list all containers on the system.
    @slip.dbus.polkit.require_auth("org.atomic.read")
    @dbus.service.method("org.atomic", in_signature='', out_signature='s')
    def ContainersList(self):
        c = Containers()
        args = self.Args()
        args.all=True
        c.set_args(args)
        return json.dumps(c.ps())

    # atomic containers section
    # The ContainersDelete method will delete one or more containers on the system.
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='asbb', out_signature='')
    def ContainersDelete(self, containers, all_containers, force):
        c = Containers()
        args = self.Args()
        args.container = containers[0]
        args.containers = containers[1:]
        args.force = force
        args.all = all_containers
        c.set_args(args)
        return c.delete()

    # The ContainersTrim method will Discard unused blocks (fstrim) on rootfs of running containers.
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='', out_signature='')
    def ContainersTrim(self):
        c = Containers()
        return c.fstrim()

    # atomic images section
    # The ImagesHelp - Display help associated with the image
    @slip.dbus.polkit.require_auth("org.atomic.read")
    @dbus.service.method("org.atomic", in_signature='s', out_signature='s')
    def ImagesHelp(self, image):
        h = AtomicHelp()
        args = self.Args()
        args.image=image
        h.set_args(args)
        return h.help()

    # atomic images section
    # The ImagesInfo - display label information about an image
    @slip.dbus.polkit.require_auth("org.atomic.read")
    @dbus.service.method("org.atomic", in_signature='sb', out_signature='s')
    def ImagesInfo(self, image, remote):
        i = Info()
        args = self.Args()
        args.image=image
        args.remote=remote
        i.set_args(args)
        return i.info()

    # atomic images section
    # The Images method will list all installed container images on the system.
    @slip.dbus.polkit.require_auth("org.atomic.read")
    @dbus.service.method("org.atomic", in_signature='', out_signature='s')
    def ImagesList(self):
        images = Images()
        args = self.Args()
        args.all=True
        images.set_args(args)
        i = images.display_all_image_info()
        return json.dumps(i)

    # atomic containers section
    # The ImagesDelete method will delete one or more images on the system.
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='asbb', out_signature='')
    def ImagesDelete(self, images, force, remote):
        i = Delete()
        args = self.Args()
        args.delete_targets = images
        args.remote = remote
        args.force = force
        i.set_args(args)
        return i.delete_image()

    # The ImagesPrune method will delete unused 'dangling' images
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='', out_signature='')
    def ImagesPrune(self):
        d = Delete()
        return d.prune_images()

    # The ImagesPull method will pull the specified image
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='sss', out_signature='')
    def ImagePull(self, image, storage, reg_type):
        p = Pull()
        args = self.Args()
        args.image = image
        args.storage = storage
        if reg_type != "":
            args.reg_type = reg_type
        p.set_args(args)
        return p.pull_image()

    # The ImagesUpdate method downloads the latest container image.
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='sb', out_signature='')
    def ImagesUpdate(self, image, force):
        u = Update()
        args = self.Args()
        args.image = image
        args.force = force
        u.set_args(args)
        return u.update()

    # The Vulnerable method will send back information that says
    # whether or not an installed container image is vulnerable
    @slip.dbus.polkit.require_auth("org.atomic.read")
    @dbus.service.method("org.atomic", in_signature='', out_signature='s')
    def VulnerableInfo(self):
        args = self.Args()
        self.atomic.set_args(args)
        return json.dumps(self.atomic.get_all_vulnerable_info())

    # atomic install section
    # The Install method will install the specified image
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='ssbbsasas', out_signature='')
    def Install(self, image, name, user, system, remote, setvalues, extra_args):
        i = Install()
        args = self.Args()
        args.image = image
        args.name = name
        args.user = user
        args.system = system
        args.remote = remote
        args.setvalues = setvalues
        args.args = extra_args
        i.set_args(args)
        return i.install()

    # atomic mount section
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='sssbb', out_signature='')
    def MountImage(self, image, mountpoint, options, live, shared):
        mount = Mount()
        mount.image = image
        mount.mountpoint = mountpoint
        args = self.Args()
        args.options = options
        args.live = live
        args.shared = shared
        self.atomic.set_args(args)
        return mount.mount()

    # atomic mount section
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='s', out_signature='')
    def UnmountImage(self, mountpoint):
        mount = Mount()
        mount.mountpoint = mountpoint
        return mount.unmount()

    # atomic run section
    # The Run method will run the specified image
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='ssbbas', out_signature='')
    def Run(self, image, name, spc, detach, command):
        r = Run()
        args = self.Args()
        args.image = image
        args.name = name
        args.spc = spc
        args.detach = detach
        args.command = command
        r.set_args(args)
        return r.run()

    # atomic scan section
    # The ScanList method will return a list of all scanners.
    @slip.dbus.polkit.require_auth("org.atomic.read")
    @dbus.service.method("org.atomic", in_signature='',
                         out_signature= 's')
    def ScanList(self):
        scan_list = Scan()
        args = self.Args()
        scan_list.set_args(args)
        return json.dumps(scan_list.get_scanners_list())

    # The ScanSetup method will create the scan object.
    def _ScanSetup(self, scan_targets, scanner, scan_type, rootfs, _all, images, containers):
        scan = Scan()
        args = self.Args()
        scan.useTTY = False
        if scan_targets:
            args.scan_targets = scan_targets
        if scanner:
            args.scanner = scanner
        if scan_type:
            args.scan_type = scan_type
        if len(scan_targets):
            args.scan_targets = scan_targets
        args.rootfs = rootfs
        args.all = _all
        args.images = images
        args.containers = containers
        scan.set_args(args)
        return scan


    # The Scan method will return a string.
    @slip.dbus.polkit.require_auth("org.atomic.read")
    @dbus.service.method("org.atomic", in_signature='asssasbbb',
                         out_signature= 's')
    def Scan(self, scan_targets, scanner, scan_type, rootfs, _all, images, containers):
        return self._ScanSetup(scan_targets, scanner, scan_type, rootfs, _all, images, containers).scan()

    # The ScheduleScan method will return a token.
    @slip.dbus.polkit.require_auth("org.atomic.read")
    @dbus.service.method("org.atomic", in_signature='asssasbbb', out_signature= 'x')
    def ScheduleScan(self, scan_targets, scanner, scan_type, rootfs, _all, images, containers):
        scan = self._ScanSetup(scan_targets, scanner, scan_type, rootfs, _all, images, containers)
        token = self.AllocateToken()
        with self.tasks_lock:
            self.tasks.append((token, scan))
        return token

    # The GetScanResults method will determine whether or not the results for
    # the token are ready.
    @slip.dbus.polkit.require_auth("org.atomic.read")
    @dbus.service.method("org.atomic", in_signature='x', out_signature= 's')
    def GetScanResults(self, token):
        with self.results_lock:
            if token in self.results:
                ret = self.results[token]
                del self.results[token]
                return ret
            else:
                return ""

    # atomic sign section
    # The create a signature for images which can be used later to verify them.
    @slip.dbus.polkit.require_auth("org.atomic.read")
    @dbus.service.method("org.atomic", in_signature='assss', out_signature='')
    def Sign(self, images, sign_by, signature_path, gnupghome):
        sign = Sign()
        args = self.Args()
        args.images = images
        args.sign_by = sign_by
        args.signature_path = signature_path
        args.gnupghome = gnupghome
        sign.set_args(args)
        return sign.sign()


    # atomic stop section
    # The Stop method will stop the specified image
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='ssas', out_signature='')
    def Stop(self, image, name, extra_args):
        i = Stop()
        args = self.Args()
        args.image = image
        args.name = name
        args.args = extra_args
        i.set_args(args)
        return i.stop()

    # atomic storage section
    # The StorageReset method deletes all containers and images from a system.
    # Resets storage to its initial configuration.
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='', out_signature='')
    def StorageReset(self):
        storage = Storage()
        # No arguments are passed for storage_reset function
        args = self.Args()
        storage.set_args(args)
        storage.reset()

    # The StorageImport method imports all containers and their associated
    # contents from a filesystem directory.
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='ss', out_signature='')
    def StorageImport(self, graph, import_location):
        storage = Storage()
        args = self.Args()
        args.graph = graph
        args.import_location = import_location
        storage.set_args(args)
        storage.Import()

    # The StorageExport method exports all containers and their associated
    # contents into a filesystem directory.
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='ssb', out_signature='')
    def StorageExport(self, graph="/var/lib/docker", export_location="/var/lib/atomic/migrate", force = False):
        storage = Storage()
        args = self.Args()
        args.graph = graph
        args.export_location = export_location
        args.force = force
        storage.set_args(args)
        storage.Export()

    # The StorageModify method modifies the default storage setup.
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='asv', out_signature='')
    def StorageModify(self, devices=None, driver = None):
        storage = Storage()
        args = self.Args()
        if devices:
            args.devices = devices
        else:
            args.devices = []
        args.driver = driver
        storage.set_args(args)
        storage.modify()

    # atomic top section
    @slip.dbus.polkit.require_auth("org.atomic.read")
    @dbus.service.method("org.atomic", in_signature='ass', out_signature='s')
    def Top(self, containers, optional):
        top = Top()
        args = self.Args()
        args.containers = containers
        args.optional = optional
        top.set_args(args)
        return top.json()

    # atomic trust section
    # The TrustShow displays system trust policy
    @slip.dbus.polkit.require_auth("org.atomic.read")
    @dbus.service.method("org.atomic", in_signature='', out_signature='s')
    def TrustShow(self):
        trust = Trust()
        args = self.Args()
        trust.set_args(args)
        return json.dumps(trust.show_json())

    # TrustAdd adds public key trust to specific registry repository
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='ssassss', out_signature='')
    def TrustAdd(self, registry, trusttype, pubkeys, keytype, sigstore, sigstoretype):
        trust = Trust()
        args = self.Args()
        args.registry = registry
        args.pubkeys = pubkeys
        args.keytype = keytype
        args.trust_type = trusttype
        args.sigstoretype = sigstoretype
        args.sigstore = sigstore
        trust.set_args(args)
        trust.add()

    # TrustAdd removes public key trust to specific registry repository
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='ss', out_signature='')
    def TrustDelete(self, registry, sigstoretype):
        trust = Trust()
        args = self.Args()
        args.sigstoretype = sigstoretype
        args.registry = registry
        trust.set_args(args)
        trust.delete()

    # TrustDefaultPolicy sets the default container image trust for the system
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='s', out_signature='')
    def TrustDefaultPolicy(self, default_policy):
        trust = Trust()
        args = self.Args()
        args.default_policy = default_policy
        trust.set_args(args)
        return trust.modify_default()

    # atomic uninstall section
    # The Uninstall method will uninstall the specified image
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='ssbas', out_signature='')
    def Uninstall(self, image, name, force, extra_args):
        i = Uninstall()
        args = self.Args()
        args.image = image
        args.name = name
        args.force = force
        args.args = extra_args
        i.set_args(args)
        return i.uninstall()

    # atomic upload section
    # atomic verify section
    # The Verify method takes in an image name and returns whether or not the
    # image should be updated
    @slip.dbus.polkit.require_auth("org.atomic.read")
    @dbus.service.method("org.atomic", in_signature='s', out_signature='s')
    def Verify(self, image):
        verifications = []
        verify = Verify()
        verify.useTTY = False
        args = self.Args()
        args.image = image
        verify.set_args(args)
        verifications.append({"Image": image,
                              "Verification": verify.verify_dbus()}) #pylint: disable=no-member
        return json.dumps(verifications)

    # atomic version section
    # The Version method takes in an image name and returns its version
    # information in a list of dicts
    @slip.dbus.polkit.require_auth("org.atomic.read")
    @dbus.service.method("org.atomic", in_signature='sb',
                         out_signature='s')
    def ImageVersion(self, image, recurse=False):
        info = Info()
        args = self.Args()
        args.image = image
        args.recurse = recurse
        info.set_args(args)
        return json.dumps(info.dbus_version())

if __name__ == "__main__":
    mainloop = GObject.MainLoop()
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    system_bus = dbus.SystemBus()

    if (system_bus.request_name("org.atomic", DBUS_NAME_FLAG_DO_NOT_QUEUE) == DBUS_REQUEST_NAME_REPLY_PRIMARY_OWNER):
        atomic_object = atomic_dbus(system_bus, "/org/atomic/object")
        slip.dbus.service.set_mainloop(mainloop)
        mainloop.run()
    else:
        print("Another process owns the 'org.atomic' D-Bus name. Exiting.")
