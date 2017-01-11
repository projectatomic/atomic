import sys
from Atomic.backendutils import BackendUtils
from Atomic.backends._docker import DockerBackend
from . import util
from Atomic.discovery import RegistryInspectError

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
    runp.add_argument("-n", "--name", dest="name", default=None,
                      help=_("name of container"))
    runp.add_argument("--spc", default=False, action="store_true",
                      help=_("use super privileged container mode: '%s'" %
                             Run.print_spc()))
    runp.add_argument("-d", "--detach", default=False, action="store_true",
                      help=_("run the container in the background"))
    runp.add_argument("image", help=_("container image"))
    runp.add_argument("command", nargs="*",
                      help=_("optional command to execute within the container. "
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
        if self.name:
            be_utils = BackendUtils()
            try:
                be, con_obj = be_utils.get_backend_and_container_obj(self.name)
                return be.run(con_obj, atomic=self, args=self.args)
            except ValueError:
                pass


        db = DockerBackend()
        img_object = db.has_image(self.image)
        if img_object is None:
            self.display("Need to pull %s" % self.image)
            if self.args.display:
                return 0
            try:
                db.pull_image(self.image)
                img_object = db.has_image(self.image)
            except RegistryInspectError:
                util.write_err("Unable to find image {}".format(self.image))

        db.run(img_object, atomic=self, args=self.args)

    @staticmethod
    def print_run():
        return "%s run %s" % (util.default_docker(), " ".join(RUN_ARGS))

    @staticmethod
    def print_spc():
        return "%s run %s" % (util.default_docker(), " ".join(SPC_ARGS))
