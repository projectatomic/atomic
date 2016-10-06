import argparse
from . import util
from .util import add_opt
from .install import INSTALL_ARGS
from docker.errors import NotFound

try:
    from . import Atomic
except ImportError:
    from atomic import Atomic # pylint: disable=relative-import

def cli(subparser):
    # atomic uninstall
    uninstallp = subparser.add_parser(
        "uninstall", help=_("execute container image uninstall method"),
        epilog="atomic uninstall attempts to read the LABEL UNINSTALL "
        "field in the image, if it does not exist atomic will "
        "remove the image from your machine.  You could add a "
        "LABEL UNINSTALL command to your Dockerfile like: 'LABEL "
        "UNINSTALL %s'" % Uninstall.print_uninstall())
    uninstallp.set_defaults(_class=Uninstall, func='uninstall')
    add_opt(uninstallp)
    uninstallp.add_argument("-n", "--name", dest="name", default=None,
                            help=_("name of container"))
    uninstallp.add_argument("-f", "--force", default=False, dest="force",
                            action="store_true",
                            help=_("remove all containers based on this "
                                   "image"))
    uninstallp.add_argument("image", help=_("container image"))
    uninstallp.add_argument("args", nargs=argparse.REMAINDER,
                            help=_("Additional arguments appended to the "
                                   "image uninstall method"))

class Uninstall(Atomic):
    def __init__(self):
        super(Uninstall, self).__init__()

    def uninstall(self):
        if self.syscontainers.get_checkout(self.args.image):
            return self.syscontainers.uninstall(self.args.image)

        self.inspect = self._inspect_container()
        if self.inspect and self.force:
            self.force_delete_containers()
        try:
            # Attempt to remove container, if it exists just return
            self.d.stop(self.name)
            self.d.remove_container(self.name)
        except NotFound:
            # On exception attempt to remove image
            pass

        self.inspect = self._inspect_image()
        if not self.inspect:
            raise ValueError("Image '%s' is not installed" % self.image)

        args = self._get_args("UNINSTALL")
        if args:
            cmd = self.gen_cmd(args + self.quote(self.args.args))
            cmd = self.sub_env_strings(cmd)
            self.display(cmd)
            util.check_call(cmd, env=self.cmd_env())

        if self.name == self.image:
            util.write_out("docker rmi %s" % self.image)
            util.check_call([self.docker_binary(), "rmi", self.image])

    @staticmethod
    def print_uninstall():
        return "%s %s %s" % (util.default_docker(), " ".join(INSTALL_ARGS), "/usr/bin/UNINSTALLCMD")

