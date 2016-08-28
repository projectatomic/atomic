import getpass
import json

from . import util
from . import pulp
from . import satellite

try:
    from . import Atomic
except ImportError:
    from atomic import Atomic # pylint: disable=relative-import

def cli(subparser):
    # atomic push
    pushp = subparser.add_parser(
        "push", aliases=['upload'], help=_("push latest image to repository"),
        epilog="push the latest specified image to a repository.")
    pushp.set_defaults(_class=Push, func='push')
    # making it so we cannot call both the --pulp and --satellite commands
    # at the same time (mutually exclusive)
    pushgroup = pushp.add_mutually_exclusive_group()
    pushgroup.add_argument("--pulp",
                           default=False,
                           action="store_true",
                           help=_("push image using pulp"))
    pushgroup.add_argument("--satellite",
                           default=False,
                           action="store_true",
                           help=_("push image using Satellite"))

    pushp.add_argument("--verify_ssl",
                         default=None,
                         action="store_true",
                         help=_("flag to verify ssl of registry"))
    pushp.add_argument("--debug",
                         default=None,
                         action="store_true",
                         help=_("debug mode"))
    pushp.add_argument("-U", "--url",
                         dest="url",
                         default=None,
                         help=_("URL for remote registry"))
    pushp.add_argument("-u", "--username",
                         default=None,
                         dest="username",
                         help=_("Username for remote registry"))
    pushp.add_argument("-p", "--password",
                         default=None,
                         dest="password",
                         help=_("Password for remote registry"))
    pushp.add_argument("image", help=_("container image"))
    pushp.add_argument("-a", "--activation_key",
                         default=None,
                         dest="activation_key",
                         help=_("Activation Key"))
    pushp.add_argument("-r", "--repository_id",
                         default=None,
                         dest="repo_id",
                         help=_("Repository ID"))
    # pushp.add_argument("--activation_key_name",
    #                      default=None,
    #                      dest="activation_key_name",
    #                      help=_("Activation Key Name"))
    # pushp.add_argument("--repo_name", "--repository_name",
    #                      default=None,
    #                      dest="repo_name",
    #                      help=_("Repository Name"))
    # pushp.add_argument("--org_name", "--organization_name",
    #                      default=None,
    #                      dest="org_name",
    #                      help=_("Organization Name"))

class Push(Atomic):
    def __init__(self):
        super(Push, self).__init__()

    def push(self):
        self.ping()
        prevstatus = ""
        # Priority order:
        # If user passes in a password/username/url/ssl flag, use that
        # If not, read from the config file
        # If still nothing, ask again for registry user/pass
        if self.args.pulp:
            config = pulp.PulpConfig().config()

        if self.args.satellite:
            config = satellite.SatelliteConfig().config()

        if (self.args.satellite | self.args.pulp):
            if not self.args.username:
                self.args.username = config["username"]
            if not self.args.password:
                self.args.password = config["password"]
            if not self.args.url:
                self.args.url = config["url"]
            if self.args.verify_ssl is None:
                self.args.verify_ssl = config["verify_ssl"]

        if self.args.verify_ssl is None:
            self.args.verify_ssl = False

        if not self.args.username:
            self.args.username = util.input("Registry Username: ")

        if not self.args.password:
            self.args.password = getpass.getpass("Registry Password: ")

        if (self.args.satellite | self.args.pulp):
            if not self.args.url:
                self.args.url = util.input("URL: ")

        if self.args.pulp:
            return pulp.push_image_to_pulp(self.image, self.args.url,
                                           self.args.username,
                                           self.args.password,
                                           self.args.verify_ssl,
                                           self.d)

        if self.args.satellite:
            if not self.args.activation_key:
                self.args.activation_key = util.input("Activation Key: ")
            if not self.args.repo_id:
                self.args.repo_id = util.input("Repository ID: ")
            return satellite.push_image_to_satellite(self.image,
                                                     self.args.url,
                                                     self.args.username,
                                                     self.args.password,
                                                     self.args.verify_ssl,
                                                     self.d,
                                                     self.args.activation_key,
                                                     self.args.repo_id,
                                                     self.args.debug)

        else:
            self.d.login(self.args.username, self.args.password)
            for line in self.d.push(self.image, stream=True):
                bar = json.loads(line)
                status = bar['status']
                if prevstatus != status:
                    util.write_out(status, "")
                if 'id' not in bar:
                    continue
                if status == "Uploading":
                    util.write_out(bar['progress'] + " ")
                elif status == "Push complete":
                    pass
                elif status.startswith("Pushing"):
                    util.write_out("Pushing: " + bar['id'])

                prevstatus = status
