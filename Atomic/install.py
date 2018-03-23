import argparse
import re
import sys
from . import util
from .util import add_opt
from .syscontainers import OSTREE_PRESENT
from Atomic.backendutils import BackendUtils
from Atomic.discovery import RegistryInspectError
from time import gmtime, strftime

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

ATOMIC_CONFIG = util.get_atomic_config()
_storage = ATOMIC_CONFIG.get('default_storage', "docker")

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
    installp.add_argument("--storage", dest="storage", default=None,
                   help=_("Specify the storage. Default is currently '%s'.  You can"
                          " change the default by editing /etc/atomic.conf and changing"
                          " the 'default_storage' field." % _storage))
    installp.add_argument("-n", "--name", dest="name", default=None,
                          help=_("name of container"))
    installp.add_argument(
        "--display",
        default=False,
        action="store_true",
        help=_("preview the command that %s would execute") % sys.argv[0])
    installp.add_argument("image", help=_("container image"))
    if OSTREE_PRESENT:
        system_xor_user = installp.add_mutually_exclusive_group()
        system_xor_user.add_argument("--user", dest="user", action="store_true", default=False,
                                     help=_("install the image as an user image."))
        system_xor_user.add_argument("--system", dest="system",
                                     action='store_true', default=False,
                                     help=_('install a system container'))
        installp.add_argument("--runtime", dest="runtime", default=None,
                              help=_('specify the OCI runtime to use for system and user containers'))
        installp.add_argument("--rootfs", dest="remote",
                              help=_("choose an existing exploded container/image to use "
                                     "its rootfs as a remote, read-only rootfs for the "
                                     "container to be installed"))
        installp.add_argument("--set", dest="setvalues",
                              action='append',
                              help=_("specify a variable in the VARIABLE=VALUE "
                                     "form for a system container"))
    installp.add_argument("--system-package", dest="system_package", default="auto",
                          help=_('control how to install the package.  It accepts `auto`, `yes`, `no`, `build`'))
    installp.add_argument("args", nargs=argparse.REMAINDER,
                          help=_("additional arguments appended to the image "
                                 "install method"))


class Install(Atomic):
    def install(self):
        if self.args.debug:
            util.write_out(str(self.args))
        storage_set = False if self.args.storage is None else True
        storage = _storage if not storage_set else self.args.storage
        args_system = getattr(self.args, 'system', None)
        args_user = getattr(self.args, 'user', None)
        if (args_system or args_user) and storage != 'ostree' and storage_set:
            raise ValueError("The --system and --user options are only available for the 'ostree' storage.")
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
        if self.ostree_uri(self.image):
            return self.syscontainers.install(self.image, self.name)
        # Check if image exists
        str_backend = 'ostree' if args_system else self.args.storage or storage
        be = be_utils.get_backend_from_string(str_backend)
        img_obj = be.has_image(self.args.image)
        if img_obj and img_obj.is_system_type:
            be = be_utils.get_backend_from_string('ostree')

        if img_obj is None:
            # Unable to find the image locally, look remotely
            remote_image_obj = be.make_remote_image(self.args.image)
            # We found an atomic.type of system, therefore install it onto the ostree
            # backend
            if remote_image_obj.is_system_type and not storage_set and not (args_system or args_user):
                be_utils.message_backend_change('docker', 'ostree')
                be = be_utils.get_backend_from_string('ostree')
            be.pull_image(self.args.image, remote_image_obj, debug=self.args.debug)
            img_obj = be.has_image(self.image)

        if be.backend is not 'docker':
            if OSTREE_PRESENT and self.args.setvalues and not self.user and not self.system:
                raise ValueError("--set is valid only when used with --system or --user")

            # We need to fix this long term and get ostree
            # using the backend approach vs the atomic args
            be.syscontainers.set_args(self.args)
            return be.install(self.image, self.name)

        installation = None
        if storage == 'docker' and not args_system:
            if self.args.system_package == 'build':
                raise ValueError("'--system-package=build' is not supported for docker backend")
            installation = be.rpm_install(img_obj, self.name)

        install_args = img_obj.get_label('INSTALL')

        if installation or install_args:
            try:
                name = img_obj.fq_name
            except RegistryInspectError:
                name = img_obj.input_name
            install_data_content = {
                'id': img_obj.id,
                "container_name": self.name,
                'install_date': strftime("%Y-%m-%d %H:%M:%S", gmtime())
            }
            if installation:
                # let's fail the installation if rpm for this image is already installed
                if util.InstallData.image_installed(img_obj):
                    raise ValueError("Image {} is already installed.".format(self.image))
                install_data_content["rpm_installed_files"] = installation.installed_files
                rpm_nvra = re.sub(r"\.rpm$", "", installation.original_rpm_name)
                install_data_content["system_package_nvra"] = rpm_nvra
            install_data = {name: install_data_content}

        if not install_args:
            return 0
        install_args = install_args.split()
        cmd = self.sub_env_strings(self.gen_cmd(install_args + self.quote(self.args.args)))
        self.display(cmd)

        if not self.args.display:
            result = util.check_call(cmd)
            if result == 0:
                if installation or install_args:
                    # Only write the install data if the installation worked.
                    util.InstallData.write_install_data(install_data, append=True)
            return result



    @staticmethod
    def print_install():
        return "%s %s %s" % (util.default_docker(), " ".join(INSTALL_ARGS), "/usr/bin/INSTALLCMD")

    @staticmethod
    def ostree_uri(image_name):
        for i in ['dockertar:', 'docker:']:
            if image_name.startswith(i):
                return True
        return False
