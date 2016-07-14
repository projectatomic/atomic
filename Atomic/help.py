from . import Atomic
import subprocess
from pydoc import pager
import os
from . import mount
import sys
from . import util


class AtomicHelp(Atomic):

    def __init__(self):
        super(AtomicHelp, self).__init__()
        self.mount_location = '/run/atomic'
        self.help_file_name = 'help.1'
        self.docker_object = None
        self.is_container = True
        self.use_pager = True
        self.alt_help_cmd = None
        self.image = None
        self.inspect = None

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
            self.display_alt_help()
        else:
            self.display_man_help(docker_id)

    def display_man_help(self, docker_id):
        """
        Display the help for a container or image using the default
        method of displaying a man formatted page
        :param docker_id: docker object to get help for
        :return: None
        """
        if not os.path.exists(self.mount_location):
            os.mkdir(self.mount_location)
        # Set the pager to less -R
        enc = sys.getdefaultencoding()
        if sys.stdout.isatty():
            os.environ['PAGER'] = '/usr/bin/less -R'
        else:
            # There is no tty
            self.use_pager = False
        dm = mount.DockerMount(self.mount_location, mnt_mkdir=True)
        mnt_path = dm.mount(docker_id)
        try:
            help_file = open(os.path.join(mnt_path, self.help_file_name))
        except IOError:
            pass
        try:
            help_file = open(os.path.join(mnt_path, 'rootfs', self.help_file_name))
        except IOError:
            dm.unmount(path=mnt_path)
            raise ValueError("Unable to find help file for {}".format(self.docker_object))

        cmd2 = ['groff', '-man', '-Tascii']
        c2 = subprocess.Popen(cmd2, stdin=help_file, stdout=subprocess.PIPE, close_fds=True)
        result = c2.communicate()[0].decode(enc)
        help_file.close()
        if not self.use_pager:
            util.write_out("\n{}\n".format(result))
        else:
            # Call the pager
            pager(result)

        # Clean up
        dm.unmount(path=mnt_path)

    def display_alt_help(self):
        """
        Displays help when the HELP LABEL override is being used.
        :return: None
        """
        cmd = self.gen_cmd(self.alt_help_cmd.split(" "))
        cmd = self.sub_env_strings(cmd)
        self.display(cmd)
        util.check_call(cmd, env=self.cmd_env())
