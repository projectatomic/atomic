import errno
import shutil
import selinux
import requests
import os, sys

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
    from atomic import Atomic

class Storage(Atomic):
    dss_conf = "/etc/sysconfig/docker-storage-setup"
    dss_conf_bak = dss_conf + ".bkp"

    def reset(self):
        root = "/var/lib/docker"
        try:
            self.d.info()
            raise ValueError("Docker daemon must be stopped before resetting storage")
        except requests.exceptions.ConnectionError as e:
            pass

        util.check_call(["docker-storage-setup", "--reset"], stdout=DEVNULL)
        util.call(["umount", root + "/devicemapper"], stderr=DEVNULL)
        util.call(["umount", root + "/overlay"], stderr=DEVNULL)
        shutil.rmtree(root)
        os.mkdir(root)
        try:
            selinux.restorecon(root.encode("utf-8"))
        except:
            selinux.restorecon(root)

    def modify(self):
        try:
            shutil.copyfile(self.dss_conf, self.dss_conf_bak)
            if len(self.args.devices) > 0:
                self._add_device(self.args.devices)
            if self.args.driver:
                self._driver(self.args.driver)
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

    def _driver(self, driver):
        util.sh_modify_var_in_file(self.dss_conf, "STORAGE_DRIVER",
                                   lambda old: driver)

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
