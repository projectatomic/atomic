from . import Atomic
import argparse
import tempfile
from pydoc import pager
import os
from . import mount
import sys
from . import util

def cli(subparser, hidden=False):
    #atomic help
    if hidden:
        helpp = subparser.add_parser("help", argument_default=argparse.SUPPRESS)

    else:
        helpp = subparser.add_parser("help",
                                     help=_("display help associated with the image"),
                                     epilog="atomic help 'image'")

    helpp.set_defaults(_class=AtomicHelp, func='help_tty')
    helpp.add_argument("image", help=_("Image ID or name"))


GROFF_BINARY = "/usr/bin/groff"


class AtomicHelp(Atomic):
    ATOMIC_DIR="/run/atomic"

    def __init__(self):
        super(AtomicHelp, self).__init__()
        if not os.path.exists(self.ATOMIC_DIR):
            os.makedirs(self.ATOMIC_DIR)

        # possible filenames for help file inside container
        self.help_file_candidates = (
            # help filename inside image, command to process the help file before displaying
            ("help.1", (GROFF_BINARY, '-t', '-man', '-Tascii')),
            ("README.md", None)
        )

        self.docker_object = None
        self.is_container = True
        self.use_pager = True
        self.image = None
        self.inspect = None
        self.enc = sys.getdefaultencoding()

    def help_tty(self):
        result = self.help()
        if not sys.stdout.isatty():
            util.write_out("\n{}\n".format(result))
        else:
            # Call the pager
            os.environ['PAGER'] = '/usr/bin/less -R'
            pager(result.decode(self.enc))

    def help(self):
        """
        Displays help text for a container.
        :return: None
        """
        self.docker_object = self.args.image
        docker_id = self.get_input_id(self.docker_object)
        self.inspect = self._inspect_container(docker_id)
        if self.inspect is None:  # docker_id is an image
            self.inspect = self._inspect_image(docker_id)
            self.is_container = False
        else:
            # The docker object is a container, need to set
            # its image
            self.image = self.inspect['Image']

        try:
            return self.man_help(docker_id)
        except ValueError:
            # Check if "help" label is provided
            # The label contains command which will be executed
            help_cmd = self._get_args('HELP')
            if help_cmd:
                return self.alt_help(help_cmd)
            else:
                raise ValueError("There is no help for {}.".format(self.docker_object))

    def man_help(self, docker_id):
        """
        Display the help for a container or image using the default
        method of displaying a man formatted page
        :param docker_id: docker object to get help for
        :return: None
        """
        mount_location = tempfile.mkdtemp(prefix=self.ATOMIC_DIR)
        try:
            dm = mount.DockerMount(mount_location)
            with mount.MountContextManager(dm, docker_id):
                # defined b/c of pylint, this is not needed due to for & else construct
                candidate_file = None
                candidate_preprocessor = None
                for candidate_file, candidate_preprocessor in self.help_file_candidates:
                    # overlay
                    help_path = os.path.join(dm.mountpoint, candidate_file)
                    if not os.path.exists(help_path):
                        # devicemapper
                        help_path = os.path.join(dm.mountpoint, 'rootfs', candidate_file)
                    if os.path.exists(help_path):
                        break
                else:
                    # not found
                    raise ValueError(
                        "Unable to find help file for {}.\nTried these files {}.".format(
                            self.docker_object, [x[0] for x in self.help_file_candidates])
                    )

                with open(help_path, "r") as help_file:
                    if candidate_preprocessor:
                        if not os.path.exists(candidate_preprocessor[0]):
                            raise IOError(
                                "Cannot display help file {} for {}: {} unavailable".format(
                                    candidate_file, self.docker_object, candidate_preprocessor)
                            )

                        return util.check_output(candidate_preprocessor, stdin=help_file)
                    return help_file.read()
        finally:
            os.rmdir(mount_location)

    def alt_help(self, help_cmd):
        """
        Returns help when the HELP LABEL override is being used.
        :return: None
        """
        cmd = self.gen_cmd(help_cmd)
        cmd = self.sub_env_strings(cmd)
        self.display(cmd)
        return util.check_output(cmd, env=self.cmd_env()).decode(self.enc)
