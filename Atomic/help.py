from . import Atomic
import argparse
import subprocess
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

class AtomicHelp(Atomic):
    ATOMIC_DIR="/run/atomic"
    def __init__(self):
        super(AtomicHelp, self).__init__()
        if not os.path.exists(self.ATOMIC_DIR):
            os.makedirs(self.ATOMIC_DIR)
        self.mount_location = tempfile.mkdtemp(prefix=self.ATOMIC_DIR)
        self.help_file_name = 'help.1'
        self.docker_object = None
        self.is_container = True
        self.use_pager = True
        self.alt_help_cmd = None
        self.image = None
        self.inspect = None

    def help_tty(self):
        result = self.help()
        if not sys.stdout.isatty():
            util.write_out("\n{}\n".format(result))
        else:
            # Call the pager
            os.environ['PAGER'] = '/usr/bin/less -R'
            pager(result)

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

        # Check if an alternate help command is provided
        labels = self._get_labels()
        self.alt_help_cmd = None if len(labels) == 0 else labels.get('HELP')

        if self.alt_help_cmd is not None:
            return self.alt_help()
        else:
            return self.man_help(docker_id)

    def man_help(self, docker_id):
        """
        Display the help for a container or image using the default
        method of displaying a man formatted page
        :param docker_id: docker object to get help for
        :return: None
        """
        if not os.path.exists(self.mount_location):
            os.makedirs(self.mount_location)
        # Set the pager to less -R
        enc = sys.getdefaultencoding()
        dm = mount.DockerMount(self.mount_location, mnt_mkdir=True)
        mnt_path = dm.mount(docker_id)
        help_path = os.path.join(mnt_path, self.help_file_name)
        if not os.path.exists(help_path):
            help_path = os.path.join(mnt_path, 'rootfs', self.help_file_name)
        try:
            help_file=open(help_path)
        except IOError:
            dm.unmount(path=mnt_path)
            raise ValueError("Unable to find help file for {}".format(self.docker_object))

        cmd2 = ['/usr/bin/groff', '-man', '-Tascii']
        if not os.path.exists(cmd2[0]):
            raise IOError("Cannot display help file for {}: groff unavailable".format(self.docker_object))

        c2 = subprocess.Popen(cmd2, stdin=help_file, stdout=subprocess.PIPE, close_fds=True)
        result = c2.communicate()[0].decode(enc)
        help_file.close()
        # Clean up
        dm.unmount(path=mnt_path)
        return result

    def alt_help(self):
        """
        Returns help when the HELP LABEL override is being used.
        :return: None
        """
        cmd = self.gen_cmd(self.alt_help_cmd.split(" "))
        cmd = self.sub_env_strings(cmd)
        self.display(cmd)
        return util.check_output(cmd, env=self.cmd_env())
