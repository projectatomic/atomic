import shutil
import selinux
import requests
import os

from . import util
from .Export import export_docker
from .Import import import_docker
from .util import NoDockerDaemon

try:
    from subprocess import DEVNULL  # pylint: disable=no-name-in-module
except ImportError:
    DEVNULL = open(os.devnull, 'wb')

try:
    from . import Atomic
except ImportError:
    from atomic import Atomic # pylint: disable=relative-import

def query_lvs(lvol, vgroup, fields):
    return util.check_output([ "lvs", "--noheadings", "-o",  fields, "--unit", "b", vgroup + "/" + lvol ]).split()

def query_pvs(pv, fields):
    return util.check_output([ "pvs", "--noheadings", "-o",  fields, "--unit", "b", pv ]).split()

def list_pvs(vgroup):
    res = [ ]
    for l in util.check_output([ "pvs", "--noheadings", "-o",  "vg_name,pv_name" ]).splitlines():
        fields = l.split()
        if len(fields) == 2 and fields[0] == vgroup:
            res.append(fields[1])
    return res

def list_lvs(vgroup):
    return map(lambda s: s.strip(), # pylint: disable=deprecated-lambda, map-builtin-not-iterating
               util.check_output([ "lvs", "--noheadings", "-o", "name", vgroup ]).splitlines()) 
def list_parents(dev):
    return util.check_output([ "lsblk", "-snlp", "-o", "NAME", dev ]).splitlines()[1:]

def list_children(dev):
    return util.check_output([ "lsblk", "-nlp", "-o", "NAME", dev ]).splitlines()[1:]

def get_dss_vgroup(conf):
    vgroup = util.sh_get_var_in_file(conf, "VG", "")
    if vgroup == "":
        for l in open("/proc/mounts", "r").readlines():
            fields = l.split()
            if fields[1] == "/" and fields[0].startswith("/dev"):
                vgroup = util.check_output([ "lvs", "--noheadings", "-o",  "vg_name", fields[0]]).strip()
    return vgroup

def get_dss_devs(conf):
    return util.sh_get_var_in_file(conf, "DEVS", "").split()

class Storage(Atomic):
    dss_conf = "/etc/sysconfig/docker-storage-setup"
    dss_conf_bak = dss_conf + ".bkp"

    def reset(self):
        root = "/var/lib/docker"
        try:
            self.d.info()
            raise ValueError("Docker daemon must be stopped before resetting storage")
        except requests.exceptions.ConnectionError:
            pass

        util.check_call(["docker-storage-setup", "--reset"], stdout=DEVNULL)
        util.call(["umount", root + "/devicemapper"], stderr=DEVNULL)
        util.call(["umount", root + "/overlay"], stderr=DEVNULL)
        shutil.rmtree(root)
        os.mkdir(root)
        try:
            selinux.restorecon(root.encode("utf-8"))
        except (TypeError, OSError):
            selinux.restorecon(root)

    def modify(self):
        try:
            shutil.copyfile(self.dss_conf, self.dss_conf_bak)
            if len(self.args.devices) > 0:
                self._add_device(self.args.devices)
            if len(self.args.remove_devices) > 0:
                self._remove_devices(self.args.remove_devices, only_unused=False)
            if self.args.remove_unused_devices:
                self._remove_devices(get_dss_devs(self.dss_conf), only_unused=True)
            if self.args.driver:
                self._driver(self.args.driver)
            if self.args.vgroup is not None:
                self._vgroup(self.args.vgroup)
            if util.call(["docker-storage-setup"]) != 0:
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
            export_docker(self.args.graph, self.args.export_location, self.force)
        except requests.exceptions.ConnectionError:
            raise NoDockerDaemon()

    def Import(self):
        self.ping()
        try:
            import_docker(self.args.graph, self.args.import_location)
        except requests.exceptions.ConnectionError:
            raise NoDockerDaemon()
