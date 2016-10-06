import argparse

from . import util
from .util import DockerObjectNotFound

try:
    from . import Atomic
except ImportError:
    from atomic import Atomic # pylint: disable=relative-import

def cli(subparser):
    # atomic stop
    stopp = subparser.add_parser(
        "stop", help=_("execute container image stop method"),
        epilog="atomic will just stop the container if it is running, if "
        "image does not specify LABEL STOP")
    stopp.set_defaults(_class=Stop, func='stop')
    util.add_opt(stopp)
    stopp.add_argument("-n", "--name", dest="name", default=None,
                       help=_("name of container"))
    stopp.add_argument("image", help=_("container image"))
    stopp.add_argument("args", nargs=argparse.REMAINDER,
                          help=_("Additional arguments appended to the image "
                                 "stop method"))

class Stop(Atomic):
    def __init__(self):
        super(Stop, self).__init__()

    def stop(self):
        if self.syscontainers.get_checkout(self.name) is not None:
            self.syscontainers.stop_service(self.name)
            return

        self.inspect = self._inspect_container()
        if self.inspect is None:
            self.inspect = self._inspect_image()
            if self.inspect is None:
                raise DockerObjectNotFound(self.name)

        args = self._get_args("STOP")
        if args:
            cmd = self.gen_cmd(args + self.quote(self.args.args))
            cmd = self.sub_env_strings(cmd)
            self.display(cmd)
            util.check_call(cmd, env=self.cmd_env())

        # Container exists
        try:
            if self.inspect["State"]["Running"]:
                self.d.stop(self.name)
        except KeyError:
            pass
