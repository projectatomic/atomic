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
    def reset(self):
        root = "/var/lib/docker"
        try:
            self.d.info()
            raise ValueError("Docker daemon must be stop before resetting storage")
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
