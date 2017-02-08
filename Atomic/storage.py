import shutil
import selinux
import requests
import os

from . import util
from .Export import export_docker
from .Import import import_docker
from .util import NoDockerDaemon, default_docker_lib
import subprocess

try:
    from subprocess import DEVNULL  # pylint: disable=no-name-in-module
except ImportError:
    DEVNULL = open(os.devnull, 'wb')

try:
    from . import Atomic
except ImportError:
    from atomic import Atomic # pylint: disable=relative-import

def cli(subparser):
    # atomic storage
    storagep = subparser.add_parser(
        "storage", aliases=['migrate'], help=_("manage container storage"),
        epilog="atomic storage command allows you to setup/reset "
        "container storage")
    storage_subparser = storagep.add_subparsers(help=_("storage commands"))
    # atomic storage export
    exportp = storage_subparser.add_parser("export",
                                           help=_("export containers and associated contents into a filesystem directory"),
                                           epilog="Export containers. "
                                           "The export command exports images, "
                                           "containers, and volumes into a filesystem directory.")
    exportp.set_defaults(_class=Storage, func='Export')
    exportp.add_argument("--graph", dest="graph",
                         default=default_docker_lib(),
                         help=_("Root of the Docker runtime (Default: %s)" % default_docker_lib()))
    exportp.add_argument("--dir", dest="export_location",
                         default="/var/lib/atomic/migrate",
                         help=_("Path for exporting container's content (Default: /var/lib/atomic/migrate)"))

    # atomic storage import
    importp = storage_subparser.add_parser("import", help=_("import containers associated contents from a filesystem directory"),
                                           epilog="Import containers. "
                                           "The import command imports images,"
                                           "containers, and volumes from a filesystem directory.")
    importp.set_defaults(_class=Storage, func='Import')
    importp.add_argument("--graph", dest="graph",
                         default=default_docker_lib(),
                         help=_("Root of the Docker runtime (Default: %s)" % default_docker_lib()))

    importp.add_argument("--dir", dest="import_location",
                         default="/var/lib/atomic/migrate",
                         help=_("Path for importing container's content (Default: /var/lib/atomic/migrate)"))

    # atomic storage modify
    modifyp = storage_subparser.add_parser("modify",help='modify default storage setup')
    modifyp.add_argument('--add-device', metavar="DEVICE", dest="devices", default=[], action='append',
                         help=_("add block devices to storage pool"))
    modifyp.add_argument('--remove-device', metavar="DEVICE", dest="remove_devices", default=[], action='append',
                         help=_("remove block devices from storage pool"))
    modifyp.add_argument('--remove-unused-devices', action='store_true',
                         help=_("remove all unused block devices from storage pool"))
    modifyp.add_argument('--driver', dest="driver", default=None, help='The storage backend driver', choices=['devicemapper', 'overlay', 'overlay2'])
    modifyp.add_argument('--vgroup', dest="vgroup", default=None, help='The storage volume group')
    modifyp.add_argument("--graph", dest="graph",
                        default=default_docker_lib(),
                        help=_("Root of the Docker runtime (Default: %s)" % default_docker_lib()))
    modifyp.set_defaults(_class=Storage, func='modify')

    # atomic storage reset
    resetp = storage_subparser.add_parser("reset",
                                          help=_("delete all containers/images from your system. Reset storage to its initial configuration."))
    resetp.add_argument("--graph", dest="graph",
                        default=default_docker_lib(),
                        help=_("Root of the Docker runtime (Default: %s)" % default_docker_lib()))
    resetp.set_defaults(_class=Storage, func='reset')

def query_pvs(pv, fields):
    return util.check_output([ "pvs", "--noheadings", "-o",  fields, "--unit", "b", pv ]).decode('utf-8').split()

def list_pvs(vgroup):
    res = [ ]
    if vgroup:
        for l in util.check_output([ "pvs", "--noheadings", "-o",  "vg_name,pv_name" ]).splitlines():
            fields = l.decode('utf-8').split()
            if len(fields) == 2 and fields[0] == vgroup:
                res.append(fields[1])
    return res

def list_lvs(vgroup):
    if vgroup:
        return map(lambda s: s.strip(), # pylint: disable=deprecated-lambda, map-builtin-not-iterating
                   util.check_output([ "lvs", "--noheadings", "-o", "name", vgroup ]).decode('utf-8').splitlines())
    else:
        return [ ]

def list_parents(dev):
    output = util.check_output([ "lsblk", "-snlp", "-o", "NAME", dev ]).decode('utf-8').strip().split()
    output.sort()
    return output[:1]

def list_children(dev):
    return util.check_output([ "lsblk", "-nlp", "-o", "NAME", dev ]).decode('utf-8').splitlines()[1:]

def get_dss_vgroup(conf):
    vgroup = util.sh_get_var_in_file(conf, "VG", "")
    if vgroup == "":
        for l in open("/proc/mounts", "r").readlines():
            fields = l.split()
            if fields[1] == "/" and fields[0].startswith("/dev"):
                vgroup = util.check_output([ "lvs", "--noheadings", "-o",  "vg_name", fields[0]]).decode('utf-8').strip()
    return vgroup

def get_dss_devs(conf):
    return util.sh_get_var_in_file(conf, "DEVS", "").split()

class Storage(Atomic):
    dss_conf = "/etc/sysconfig/docker-storage-setup"
    dss_conf_bak = dss_conf + ".bkp"

    def __init__(self):
        super(Storage, self).__init__()
        self.graphdir = None

    def set_args(self, args):
        Atomic.set_args(self, args)
        if 'graph' in self.args and self.args.graph:
            self.graphdir = self.args.graph
        else:
            if os.path.exists("/var/lib/docker") and os.path.exists("/var/lib/docker-latest"):
                raise ValueError("You must specify the --graph storage path to reset /var/lib/docker or /var/lib/docker-latest")
            if os.path.exists("/var/lib/docker"):
                self.graphdir = "/var/lib/docker"
            else:
                if os.path.exists("/var/lib/docker-latest"):
                    self.graphdir = "/var/lib/docker-latest"
                else:
                    raise ValueError("Could not find any default graph storage path. Specify one using --graph option")

    def reset(self):
        root=self.graphdir
        try:
            self.d.info()
            raise ValueError("Docker daemon must be stopped before resetting storage")
        except requests.exceptions.ConnectionError:
            pass

        util.check_call(["docker-storage-setup", "--reset"], stdout=DEVNULL)
        util.call(["umount", root + "/devicemapper"], stderr=DEVNULL)
        util.call(["umount", root + "/overlay"], stderr=DEVNULL)
        util.call(["umount", root + "/overlay2"], stderr=DEVNULL)
        shutil.rmtree(root)
        os.mkdir(root)
        try:
            selinux.restorecon(root.encode("utf-8"))
        except (TypeError, OSError):
            selinux.restorecon(root)

    def modify(self):
        try:
            shutil.copyfile(self.dss_conf, self.dss_conf_bak)
            if len(self.args.remove_devices) > 0:
                self._remove_devices(self.args.remove_devices, only_unused=False)
            if self.args.remove_unused_devices:
                self._remove_devices(get_dss_devs(self.dss_conf), only_unused=True)
            if self.args.driver:
                self._driver(self.args.driver)
            if self.args.vgroup is not None:
                self._vgroup(self.args.vgroup)
            if len(self.args.devices) > 0:
                self._add_device(self.args.devices)
            try:
                util.check_output(["docker-storage-setup"], stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as e:
                util.write_out("Return Code: {}".format(e.returncode))
                util.write_out("Failure: {}".format(e.output))
                os.rename(self.dss_conf_bak, self.dss_conf)
                util.call(["docker-storage-setup"])
                raise ValueError("docker-storage-setup failed")
        except:
            if os.path.exists(self.dss_conf_bak):
                os.rename(self.dss_conf_bak, self.dss_conf)
            raise
        finally:
            if os.path.exists(self.dss_conf_bak):
                os.remove(self.dss_conf_bak)

    def _add_device(self, devices):
        util.sh_modify_var_in_file(self.dss_conf, "DEVS",
                                   lambda old: util.sh_set_add(old, devices))

    def _remove_devices(self, devices, only_unused):
        vgroup = get_dss_vgroup(self.dss_conf)
        pvs = list_pvs(vgroup)
        lvs = list_lvs(vgroup)
        n_pvs = len(pvs)
        devices = set(devices)
        parents = None
        for pv in pvs:
            parents = list_parents(pv)
            if set(parents).isdisjoint(devices):
                continue
            devices -= set(parents)

            if query_pvs(pv, "pv_used")[0][:-1] != '0':
                if only_unused:
                    continue
                else:
                    util.check_call([ "pvmove", pv ])

            if n_pvs > 1:
                util.check_call([ "vgreduce", vgroup, pv ])
            elif len(lvs) == 0:
                util.check_call([ "vgremove", vgroup ])
            n_pvs -= 1
            util.check_call([ "wipefs", "-a", pv ])
            util.sh_modify_var_in_file(self.dss_conf, "DEVS",
                                       lambda old: util.sh_set_del(old, parents))
            if len(parents) == 1:
                children = list_children(parents[0])
                if len(children) == 1 and children[0] == pv:
                    util.check_call([ "wipefs", "-a", parents[0] ])
        if len(devices) > 0:
            raise ValueError("Not part of the storage pool: {}".format(", ".join(devices)))

    def _driver(self, driver):
        util.sh_modify_var_in_file(self.dss_conf, "STORAGE_DRIVER",
                                   lambda old: driver)

    def _vgroup(self, vgroup):
        util.sh_modify_var_in_file(self.dss_conf, "VG",
                                   lambda old: vgroup)

    def Export(self):
        try:
            export_docker(self.graphdir, self.args.export_location, self.args.assumeyes)
        except requests.exceptions.ConnectionError:
            raise NoDockerDaemon()

    def Import(self):
        self.ping()
        try:
            import_docker(self.graphdir, self.args.import_location, self.args.assumeyes)
        except requests.exceptions.ConnectionError:
            raise NoDockerDaemon()
