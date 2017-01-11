import argparse
import sys
from . import util
from .util import add_opt
from .syscontainers import OSTREE_PRESENT
from Atomic.backendutils import BackendUtils

try:
    from . import Atomic
except ImportError:
    from atomic import Atomic # pylint: disable=relative-import

INSTALL_ARGS = ["run",
                "-t",
                "-i",
                "--rm",
                "--privileged",
                "-v", "/:/host",
                "--net=host",
                "--ipc=host",
                "--pid=host",
                "-e", "HOST=/host",
                "-e", "NAME=${NAME}",
                "-e", "IMAGE=${IMAGE}",
                "-e", "CONFDIR=/host/etc/${NAME}",
                "-e", "LOGDIR=/host/var/log/${NAME}",
                "-e", "DATADIR=/host/var/lib/${NAME}",
                "-e", "SYSTEMD_IGNORE_CHROOT=1", 
                "--name", "${NAME}",
                "${IMAGE}"]

def cli(subparser):
    # atomic install
    installp = subparser.add_parser(
        "install", help=_("execute container image install method"),
        epilog="atomic install attempts to read the LABEL INSTALL field "
        "in the image, if it does not exist atomic will just pull "
        "the image on to your machine.  You could add a LABEL "
        "INSTALL command to your Dockerfile like: 'LABEL INSTALL "
        "%s'" % Install.print_install())
    installp.set_defaults(_class=Install, func='install')
    add_opt(installp)
    installp.add_argument("-n", "--name", dest="name", default=None,
                          help=_("name of container"))
    installp.add_argument(
        "--display",
        default=False,
        action="store_true",
        help=_("preview the command that %s would execute") % sys.argv[0])
    installp.add_argument("image", help=_("container image"))
    if OSTREE_PRESENT:
        bwrap_oci_available = util.bwrap_oci_available()
        runc_available = util.runc_available()
        if bwrap_oci_available or runc_available:
            system_xor_user = installp.add_mutually_exclusive_group()
            if bwrap_oci_available:
                system_xor_user.add_argument("--user", dest="user", action="store_true", default=False,
                                             help=_("Flag to specify if user is non-root privileged."))
            if runc_available:
                system_xor_user.add_argument("--system", dest="system",
                                             action='store_true', default=False,
                                             help=_('install a system container'))
        installp.add_argument("--rootfs", dest="remote",
                              help=_("choose an existing exploded container/image to use "
                                     "its rootfs as a remote, read-only rootfs for the "
                                     "container to be installed"))
        installp.add_argument("--set", dest="setvalues",
                              action='append',
                              help=_("Specify a variable in the VARIABLE=VALUE "
                                     "form for a system container"))
    installp.add_argument("args", nargs=argparse.REMAINDER,
                          help=_("Additional arguments appended to the image "
                                 "install method"))


class Install(Atomic):
    def __init__(self):
        super(Install, self).__init__()

    def install(self):
        debug = self.args.debug
        if self.args.debug:
            util.write_out(str(self.args))
        be_utils = BackendUtils()
        try:
            # Check to see if the container already exists
            _, _ = be_utils.get_backend_and_container_obj(self.name)
            raise ValueError("A container '%s' is already present" % self.name)
        except ValueError:
            pass

        if self.user:
            if not util.is_user_mode():
                raise ValueError("--user does not work for privileged user")
            return self.syscontainers.install_user_container(self.image, self.name)
        elif self.system:
            return self.syscontainers.install(self.image, self.name)
        elif OSTREE_PRESENT and self.args.setvalues:
            raise ValueError("--set is valid only when used with --system or --user")

        # Assumed backend now is docker
        be = be_utils.get_backend_from_string('docker')

        # If the image is already present,
        img_obj = be.has_image(self.image)
        if img_obj is None:
            be.pull_image(self.image, debug=debug)
            img_obj = be.has_image(self.image)
        install_args = img_obj.get_label('INSTALL')
        if not install_args:
            return 0
        install_args = install_args.split()
        cmd = self.sub_env_strings(self.gen_cmd(install_args + self.quote(self.args.args)))
        self.display(cmd)

        if not self.args.display:
            return util.check_call(cmd)

    @staticmethod
    def print_install():
        return "%s %s %s" % (util.default_docker(), " ".join(INSTALL_ARGS), "/usr/bin/INSTALLCMD")

