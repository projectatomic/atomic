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
from Atomic.push import Push, REGISTRY_TYPE_CHOICES
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
from Atomic.util import Decompose
from Atomic.tag import Tag
from Atomic import util
from gi.repository import GLib

DBUS_NAME_FLAG_DO_NOT_QUEUE = 4
DBUS_REQUEST_NAME_REPLY_PRIMARY_OWNER = 1

class atomic_dbus(slip.dbus.service.Object):
    default_polkit_auth_required = "org.atomic.readwrite"

    class Args():
        def __init__(self):
            self.activation_key = None
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
            self.extra_args = None
            self.filter = None
            self.force = False
            self.gnupghome = None
            self.graph = None
            self.heading = False
            self.hotfix = False
            self.ignore = False
            self.image = None
            self.images = []
            self.import_location = None
            self.json = True
            self.keytype = None
            self.keywords = None
            self.list = False
            self.live = False
            self.mountpoint = None
            self.metadata = None
            self.name = None
            self.names_only = False
            self.no_files = False
            self.optional = None
            self.options = None
            self.os = None
            self.password = None
            self.pretty = False
            self.preview = False
            self.prune = False
            self.pubkeys = []
            self.pulp = False
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
            self.repo_id = None
            self.revision = None
            self.rootfs = []
            self.rpms = False
            self.satellite = False
            self.save = False
            self.scan_id = None
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
            self.url = None
            self.user = None
            self.username = None
            self.verbose = False
            self.verify_ssl = False
            self.src = None
            self.target = None

    def __init__(self, *p, **k):
        super(atomic_dbus, self).__init__(*p, **k)
        self.atomic = Atomic.Atomic()
        self.tasks = []
        self.tasks_lock = threading.Lock()
        self.last_token = 0
        self.scans = {}
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
    @dbus.service.method("org.atomic", in_signature='ssbbbasb',out_signature='s')
    def Diff(self, src, dest, rpms, no_files, names_only, diff_keywords, metadata):
        diff = Diff()
        args = self.Args()
        args.compares = [src, dest]
        args.verbose = True
        args.no_files = no_files
        args.names_only = names_only
        args.rpms = rpms
        args.keywords = diff_keywords
        args.metadata = metadata
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
    @dbus.service.method("org.atomic", in_signature='asbbs', out_signature='i')
    def ContainersDelete(self, containers, all_containers=False, force=False, storage=''):
        c = Containers()
        args = self.Args()
        assert(isinstance(containers, list))
        args.containers = containers
        args.force = force
        args.assumeyes = True
        args.all = all_containers
        args.storage = storage if storage is not '' else None
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
        i = images.images()
        return json.dumps(i)

    # atomic containers section
    # The ImagesDelete method will delete one or more images on the system.
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='asbbs', out_signature='i')
    def ImagesDelete(self, images, force, remote, storage):
        i = Delete()
        args = self.Args()
        args.delete_targets = images
        args.remote = remote
        args.force = force
        args.storage = storage
        args.assumeyes = True
        i.set_args(args)
        return i.delete_image()

    # atomic containers section
    # The ImagesTag method will create a tag from an existing image.
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='sss', out_signature='i')
    def ImagesTag(self, src, target, storage):
        i = Tag()
        args = self.Args()
        args.src = src
        args.target = target
        args.storage = storage
        i.set_args(args)
        return i.tag_image()

    # The ImagesPrune method will delete unused 'dangling' images
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='', out_signature='')
    def ImagesPrune(self):
        d = Delete()
        return d.prune_images()

    # The ImagesPull method will pull the specified image
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='sss', out_signature='i')
    def ImagePull(self, image, storage='', reg_type=''):
        p = Pull()
        args = self.Args()
        args.image = image
        args.storage = None if storage == '' else storage
        args.reg_type = None if reg_type == '' else reg_type
        p.set_args(args)
        try:
            return p.pull_image()
        except Exception as e:
            raise dbus.DBusException(str(e))

    # The ImagePush method will push the specific image to a registry
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='sbbbssssssss', out_signature='i')
    def ImagePush(self, image, pulp, satellite, verify_ssl, url, username, password,
                  activation_key, repo_id, registry_type, sign_by, gnupghome):
        p = Push()
        args = self.Args()
        args.image = image
        args.pulp = pulp
        args.satellite = satellite
        args.verify_ssl = verify_ssl
        args.url = None if not url else url
        args.username = None if not username else username
        args.password = None if not password else password
        args.activation_key = activation_key
        args.repo_id = repo_id
        registry = Decompose(image).registry
        if registry not in self.atomic.load_local_tokens() and not args.username or not args.password:
            raise dbus.DBusException("There is no local token and no username/password were provided.  Please try "
                                     "again with a username and password")
        if args.satellite or args.pulp:
            if not args.username or args.password:
                raise dbus.DBusException("No username or password was provided for satellite or pulp.  Please try "
                                         "again with a username and password")
            if not args.url:
                raise dbus.DBusException("No URL was provided for satellite or pulp.  Please try again "
                                         "with a defined URL.")

        if not registry_type:
            args.reg_type = 'docker'
        else:
            args.reg_type = registry_type
        if args.reg_type not in REGISTRY_TYPE_CHOICES:
            raise dbus.DBusException("Registry type must be one of '{}'.".format(REGISTRY_TYPE_CHOICES))
        args.sign_by = None if not sign_by else sign_by
        args.gnupghome = None if not gnupghome else gnupghome
        p.set_args(args)
        try:
            return p.push()


        except Exception as e:
            raise dbus.DBusException(str(e))

    # The ImagesUpdate method downloads the latest container image.
    @slip.dbus.polkit.require_auth("org.atomic.readwrite")
    @dbus.service.method("org.atomic", in_signature='sb', out_signature='i')
    def ImageUpdate(self, image, force=False):
        u = Update()
        args = self.Args()
        args.image = image
        args.name = image
        args.force = force
        u.set_args(args)
        try:
            return u.update()
        except Exception as e:
            raise dbus.DBusException(str(e))

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
    @dbus.service.method("org.atomic", in_signature='ssbbsbas', out_signature='i')
    def Install(self, image, name='', system=False, remote=False, storage='', user=False, setvalues=''):
        if not setvalues:
            setvalues = []
        assert(isinstance(setvalues, list))
        i = Install()
        args = self.Args()
        args.image = image
        args.name = name
        args.user = user
        args.system = system
        args.storage = storage
        args.remote = remote
        args.setvalues = setvalues
        args.args = []
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
    # Return a 0 or 1 for success.  Errors result in exceptions.
    @dbus.service.method("org.atomic", in_signature='ssbbbas', out_signature='i')
    def Run(self, image, name='', spc=False, detach=False, ignore=False, command=''):
        r = Run()
        args = self.Args()
        args.image = image
        args.name = name if name is not '' else None
        args.spc = spc
        args.detach = detach
        args.command = command if command is not '' else []
        args.ignore = ignore
        r.set_args(args)
        try:
            return r.run()
        except ValueError as e:
            raise dbus.DBusException(str(e))


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
        args.scan_id = None
        scan.set_args(args)
        return scan


    # The Scan method will return a string.
    @slip.dbus.polkit.require_auth("org.atomic.read")
    @dbus.service.method("org.atomic", in_signature='asssasbbb',
                         out_signature= 's')
    def Scan(self, scan_targets, scanner, scan_type, rootfs, _all, images, containers):
        return self._ScanSetup(scan_targets, scanner, scan_type, rootfs, _all, images, containers).scan()

    @slip.dbus.polkit.require_auth("org.atomic.read")
    @dbus.service.method("org.atomic", in_signature='ssss', out_signature= 's')
    # sudo busctl --system call org.atomic /org/atomic/object org.atomic ActiveScans
    # Only support scanning one image at a time via the async method
    # Same with rootfs
    def ScanAsync(self, scan_id='', scanner='', scan_type='', rootfs=''):
        if scan_id is None and rootfs is None:
            raise ValueError("You must define 'scan_id' or 'rootfs'")
        rootfs = [] if rootfs is None else [rootfs]
        if self.scans.get(scan_id, None) is not None:
            return ValueError("{} is already being scanned")
        scan_cls = self._ScanSetup([scan_id], scanner, scan_type, rootfs, False, False, False)
        worker = ScanWorker(scan_id, self, scan_cls)
        self.scans[worker.scan_id] = worker
        self.ScanStarted(worker.scan_id)
        worker.start()
        return scan_id


    @dbus.service.signal('org.atomic', signature='s')
    def ScanStarted(self, scan_id):
        pass

    @dbus.service.signal('org.atomic', signature='s')
    def ScanCompleted(self, scan_id):
        pass

    @dbus.service.method('org.atomic', in_signature='', out_signature='as')
    def ActiveScans(self):
        return [x for x in self.scans]

    def finish_scan(self, worker):
        del self.scans[worker.scan_id]
        self.ScanCompleted(worker.scan_id)

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
    @dbus.service.method("org.atomic", in_signature='s', out_signature='i')
    def Stop(self, name):
        i = Stop()
        args = self.Args()
        args.container = name
        args.args = []
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
    @dbus.service.method("org.atomic", in_signature='ssbsbas', out_signature='i')
    def Uninstall(self, image, name, force, storage, ignore, extra_args):
        i = Uninstall()
        args = self.Args()
        args.image = image
        args.name = name if name is not '' else None
        args.force = force
        args.ignore = ignore
        args.storage = storage if storage is not '' else None
        args.extra_args = [] if not extra_args else extra_args
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

    @slip.dbus.polkit.require_auth("org.atomic.read")
    @dbus.service.method("org.atomic", in_signature='s', out_signature='s')
    def GetScanResultsById(self, iid):
        vuln_summary = self.atomic.get_all_vulnerable_info()
        summary_results = vuln_summary.get(iid, None)
        if not summary_results:
            raise ValueError("No history for scan of {}".format(iid))
        file_name = summary_results.get('json_file')
        return json.dumps(util.load_scan_result_file(file_name))


class ScanWorker(threading.Thread):
    def __init__(self, scan_id, dbus_service, scan_cls):
        threading.Thread.__init__(self)
        self.seconds = 10
        self.scan_id = scan_id
        self.dbus_service = dbus_service
        self.scan_cls = scan_cls

    def run(self):
        self.scan_cls.scan()
        GLib.idle_add(lambda: self.dbus_service.finish_scan(self))

if __name__ == "__main__":
    mainloop = GObject.MainLoop()
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    system_bus = dbus.SystemBus()

    if (system_bus.request_name("org.atomic", DBUS_NAME_FLAG_DO_NOT_QUEUE) != DBUS_REQUEST_NAME_REPLY_PRIMARY_OWNER):
        print("Another process owns the 'org.atomic' D-Bus name. Exiting.")
    atomic_object = atomic_dbus(system_bus, "/org/atomic/object")
    slip.dbus.service.set_mainloop(mainloop)
    mainloop.run()

