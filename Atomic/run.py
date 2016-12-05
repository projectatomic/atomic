import sys
import os
from . import util

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

    def run(self):
        if self.syscontainers.get_checkout(self.name) is not None:
            self.syscontainers.start_service(self.name)
            return

        self.inspect = self._inspect_container()
        if self.inspect:
            self._check_latest()
            # Container exists
            if self.inspect["State"]["Running"]:
                return self._running()
            elif not self.args.display:
                return self._start()

        # Container does not exist
        self.inspect = self._inspect_image()
        if not self.inspect:
            if self.args.display:
                return self.display("Need to pull %s" % self.image)

            self.update()
            self.inspect = self._inspect_image()

        args = self._get_args("RUN")
        if args:
            args += self.command
            opts_file = self._get_args("RUN_OPTS_FILE")
            if opts_file:
                opts_file = self.sub_env_strings("".join(opts_file))
                if opts_file.startswith("/"):
                    if os.path.isfile(opts_file):
                        try:
                            self.run_opts = open(opts_file, "r").read()
                        except IOError:
                            raise ValueError("Failed to read RUN_OPTS_FILE %s" % opts_file)
                else:
                    raise ValueError("Will not read RUN_OPTS_FILE %s: not absolute path" % opts_file)
        else:
            args = [self.docker_binary(), "run"]
            if os.isatty(0):
                args += ["-t"]
            if self.args.detach:
                args += ["-d"]
            args += SPC_ARGS if self.spc else RUN_ARGS
            args += self.command if self.command else self._get_cmd()

        if len(args) > 0 and args[0] == "docker":
            args[0] = self.docker_binary()

        cmd = self.gen_cmd(args)
        cmd = self.sub_env_strings(cmd)
        self.display(cmd)
        if self.args.display:
            return

        if not self.args.quiet:
            self.check_args(cmd)
        util.check_call(cmd, env=self.cmd_env())

    @staticmethod
    def check_args(cmd):
        found_sec_arg = False
        security_args = {
            '--privileged':
                'This container runs without separation and should be '
                'considered the same as root on your system.',
            '--cap-add':
                'Adding capabilities to your container could allow processes '
                'from the container to break out onto your host system.',
            '--security-opt label:disable':
                'Disabling label separation turns off tools like SELinux and '
                'could allow processes from the container to break out onto '
                'your host system.',
            '--net=host':
                'Processes in this container can listen to ports (and '
                'possibly rawip traffic) on the host\'s network.',
            '--pid=host':
                'Processes in this container can see and interact with all '
                'processes on the host and disables SELinux within the '
                'container.',
            '--ipc=host':
                'Processes in this container can see and possibly interact '
                'with all semaphores and shared memory segments on the host '
                'as well as disables SELinux within the container.'
        }

        for sec_arg in security_args:
            if sec_arg in cmd:
                if not found_sec_arg:
                    util.write_out("\nThis container uses privileged "
                                  "security switches:")
                util.write_out("\n\033[1mINFO: {}\033[0m "
                              "\n{}{}".format(sec_arg, " " * 6,
                                              security_args[sec_arg]))
                found_sec_arg = True
        if found_sec_arg:
            util.write_out("\nFor more information on these switches and their "
                          "security implications, consult the manpage for "
                          "'docker run'.\n")

    @staticmethod
    def print_run():
        return "%s run %s" % (util.default_docker(), " ".join(RUN_ARGS))

    @staticmethod
    def print_spc():
        return "%s run %s" % (util.default_docker(), " ".join(SPC_ARGS))
