import argparse
import sys
from Atomic.backendutils import BackendUtils
from Atomic.backends._docker import DockerBackend
from . import util
from Atomic.discovery import RegistryInspectError
from .syscontainers import OSTREE_PRESENT

try:
    from . import Atomic
except ImportError:
    from atomic import Atomic # pylint: disable=relative-import

SPC_ARGS = ["-i",
            "--privileged",
            "-v", "/:/host",
            "-v", "/run:/run",
            "-v", "/etc/localtime:/etc/localtime",
            "-v", "/sys/fs/selinux:/sys/fs/selinux:ro",
            "--net=host",
            "--ipc=host",
            "--pid=host",
            "-e", "HOST=/host",
            "-e", "NAME=${NAME}",
            "-e", "IMAGE=${IMAGE}",
            "-e", "SYSTEMD_IGNORE_CHROOT=1",
            "--name", "${NAME}",
            "${IMAGE}"]

RUN_ARGS = ["-i",
            "--name", "${NAME}",
            "${IMAGE}"]

ATOMIC_CONFIG = util.get_atomic_config()
_storage = ATOMIC_CONFIG.get('default_storage', "docker")


def cli(subparser):
    # atomic run
    runp = subparser.add_parser(
        "run", help=_("execute container image run method"),
        epilog="atomic run attempts to start an existing container if a container "
        "name is specified, or execute container image run method if an image "
        "name is specified.  Defaults to the following command, if image does "
        "not specify LABEL run:\n'%s'" % Run.print_run())
    runp.set_defaults(_class=Run, func='run')
    run_group = runp.add_mutually_exclusive_group()
    util.add_opt(runp)
    runp.add_argument("--replace", "-r", dest="replace", default=False,
                      action="store_true", help=_("Replaces an existing container by the same name"
                                                  " if it exists."))
    runp.add_argument("--storage", dest="storage", default=None,
                          help=_("Specify the storage. Default is currently '%s'.  You can"
                                 " change the default by editing /etc/atomic.conf and changing"
                                 " the 'default_storage' field." % _storage))
    runp.add_argument("-n", "--name", dest="name", default=None,
                      help=_("name of container"))
    runp.add_argument("--spc", default=False, action="store_true",
                      help=_("use super privileged container mode: '%s'" %
                             Run.print_spc()))
    runp.add_argument("-d", "--detach", default=False, action="store_true",
                      help=_("run the container in the background"))
    runp.add_argument("--runtime", dest="runtime", default=None,
                      help=_('specify the OCI runtime to use for system and user containers'))
    if OSTREE_PRESENT:
        runp.add_argument("--set", dest="setvalues",
                          action='append',
                          help=_("specify a variable in the VARIABLE=VALUE "
                                 "form for a system container"))
    runp.add_argument("image", help=_("container image"))
    runp.add_argument("command", nargs=argparse.REMAINDER,
                      help=_("command to execute within the container. "
                             "If container is not running, command is appended "
                             "to the image run method"))
    run_group.add_argument("--quiet", "-q", action="store_true",
                      help=_("Be less verbose."))

    run_group.add_argument(
        "--display",
        default=False,
        action="store_true",
        help=_("preview the command that %s would execute") % sys.argv[0])


class Run(Atomic):
    def __init__(self):
        super(Run, self).__init__()
        self.RUN_ARGS = RUN_ARGS
        self.SPC_ARGS = SPC_ARGS

    def run(self):
        storage_set = False if self.args.storage is None else True
        storage = _storage if not storage_set else self.args.storage
        be_utils = BackendUtils()
        if self.name:
            try:
                be, con_obj = be_utils.get_backend_and_container_obj(self.name)
                return be.run(con_obj, atomic=self, args=self.args)
            except ValueError:
                pass
        be = be_utils.get_backend_from_string(storage)
        db = DockerBackend()
        img_object = be.has_image(self.image)
        if img_object is None and storage == 'docker':
            self.display("Need to pull %s" % self.image)
            remote_image_obj = db.make_remote_image(self.args.image)
            # If the image has a atomic.type of system, then we need to land
            # this in the ostree backend.  Install it and then start it
            # because this is run
            if remote_image_obj.is_system_type and not storage_set:
                be = be_utils.get_backend_from_string('ostree')
                be_utils.message_backend_change('docker', 'ostree')
                be.install(self.image, self.name)
                con_obj = be.has_container(self.name)
                return be.run(con_obj)
            if self.args.display:
                return 0
            try:
                db.pull_image(self.image, remote_image_obj)
                img_object = db.has_image(self.image)
            except RegistryInspectError:
                raise ValueError("Unable to find image {}".format(self.image))
        return be.run(img_object, atomic=self, args=self.args)

    @staticmethod
    def print_run():
        return "%s run %s" % (util.default_docker(), " ".join(RUN_ARGS))

    @staticmethod
    def print_spc():
        return "%s run %s" % (util.default_docker(), " ".join(SPC_ARGS))
