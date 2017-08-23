import argparse
import os

try:
    from . import Atomic
except ImportError:
    from atomic import Atomic # pylint: disable=relative-import

def _add_remainder_arg(parser):
    parser.add_argument("args", nargs=argparse.REMAINDER,
                        help=_("Additional arguments appended to the "
                               "invocation.  Use `-- --OPTION=VAL` "
                               "if you want to pass additional "
                               "unwrapped arguments to rpm-ostree."))

def cli(subparser):
    # atomic host
    hostp = subparser.add_parser("host", help=_("execute Atomic host "
                                                "commands"))
    host_subparser = hostp.add_subparsers(help=_("host commands"))

    # atomic host rollback
    rollbackp = host_subparser.add_parser(
        "rollback", help=_("switch to alternate installed tree at next boot"))
    rollbackp.set_defaults(_class=Host, func='host_rollback')
    rollbackp.add_argument("-r", "--reboot", dest="reboot",
                           action="store_true",
                           help=_("initiate a reboot after rollback is "
                                  "prepared"))
    _add_remainder_arg(rollbackp)


    # atomic host status
    statusp = host_subparser.add_parser(
        "status", help=_("list information about all deployments"))
    statusp.add_argument("-j", "--json", dest="json",
                         action="store_true",
                         help=_("Display status in JSON format"))
    statusp.add_argument("-p", "--pretty", dest="pretty",
                         action="store_true",
                         help=_("This option is deprecated and no "
                                "longer has any effect"))
    _add_remainder_arg(statusp)

    statusp.set_defaults(_class=Host, func='host_status')

    # atomic host upgrade
    upgradep = host_subparser.add_parser(
        "upgrade", help=_("upgrade to the latest Atomic tree if one "
                          "is available"))
    upgradep.set_defaults(_class=Host, func='host_upgrade')
    upgradep.add_argument("-r", "--reboot", dest="reboot",
                          action="store_true",
                          help=_("if an upgrade is available, reboot "
                                 "after deployment is complete"))
    upgradep.add_argument("--allow-downgrade", dest="downgrade",
                          action="store_true",
                          help=_("Permit deployment of chronologically older trees"))
    upgradep.add_argument("--os", dest="os",
                          help=_("Operate on provided OSNAME"))
    upgradep.add_argument("--check-diff", dest="diff",
                          action="store_true",
                          help=_("Check for upgrades and print package diff only"))
    _add_remainder_arg(upgradep)

    # atomic host rebase
    rebasep = host_subparser.add_parser(
        "rebase", help=_("Download and deploy a new origin refspec"))
    rebasep.set_defaults(_class=Host, func='host_rebase')
    rebasep.add_argument("--os", dest="os",
                         help=_("Operate on provided OSNAME"))
    rebasep.add_argument("refspec",
                         help=_("Origin refspec for new deployment"))
    _add_remainder_arg(rebasep)

    # atomic host deploy
    deployp = host_subparser.add_parser(
        "deploy", help=_("deploy a specific commit"))
    deployp.set_defaults(_class=Host, func='host_deploy')
    deployp.add_argument("revision", help=_("Checksum or version to deploy"))
    deployp.add_argument("-r", "--reboot", dest="reboot",
                         action="store_true",
                         help=_("Reboot after deployment is complete"))
    deployp.add_argument("--os", dest="os",
                         help=_("Operate on provided OSNAME"))
    deployp.add_argument("--preview", dest="preview",
                         action="store_true",
                         help=_("Just preview package differences"))
    _add_remainder_arg(deployp)

    # atomic host unlock
    unlockp = host_subparser.add_parser(
        "unlock", help=_("Make the current deployment mutable (for development or a hotfix)"))
    unlockp.set_defaults(_class=Host, func='host_unlock')
    unlockp.add_argument("--hotfix", dest="hotfix",
                         action="store_true",
                         help=_("Retain any changes after reboot"))
    _add_remainder_arg(unlockp)

    # atomic host install/uninstall
    p = host_subparser.add_parser(
        "install", help=_("Install a (layered) RPM package"))
    p.set_defaults(_class=Host, func='host_install')
    _add_remainder_arg(p)
    p = host_subparser.add_parser(
        "uninstall", help=_("Remove a layered RPM package"))
    p.set_defaults(_class=Host, func='host_uninstall')
    _add_remainder_arg(p)

class Host(Atomic):
    def __init__(self): # pylint: disable=useless-super-delegation
        super(Host, self).__init__()

    def host_status(self):
        argv = ["status"]
        if self.args.pretty:
            argv.append("--pretty")
        if self.args.json:
            argv.append("--json")
        self._rpmostree(argv)

    def host_upgrade(self):
        argv = ["upgrade"]
        if self.args.reboot:
            argv.append("--reboot")
        if self.args.os:
            argv.append("--os=" % self.args.os )
        if self.args.diff:
            argv.append("--check-diff")
        if self.args.downgrade:
            argv.append("--allow-downgrade")
        self._rpmostree(argv)

    def host_rollback(self):
        argv = ["rollback"]
        if self.args.reboot:
            argv.append("--reboot")
        self._rpmostree(argv)

    def host_rebase(self):
        argv = ["rebase", self.args.refspec]
        if self.args.os:
            argv.append("--os=" % self.args.os )
        self._rpmostree(argv)

    def host_deploy(self):
        argv = ["deploy", self.args.revision]
        if self.args.reboot:
            argv.append("--reboot")
        if self.args.os:
            argv.append("--os=" % self.args.os)
        if self.args.preview:
            argv.append("--preview")
        self._rpmostree(argv)

    def host_unlock(self):
        argv = ['unlock']
        if self.args.hotfix:
            argv.append("--hotfix")
        self._ostreeadmin(argv)

    def host_install(self):
        argv = ['install']
        self._rpmostree(argv)

    def host_uninstall(self):
        argv = ['uninstall']
        self._rpmostree(argv)

    def _passthrough(self, args):
        cmd = args[0]
        aargs = self.args.args
        if len(aargs) > 0 and aargs[0] == "--":
            aargs = aargs[1:]
        os.execl("/usr/bin/" + cmd, *(args + aargs))

    def _rpmostree(self, args):
        self._passthrough(['rpm-ostree'] + args)

    def _ostreeadmin(self, args):
        self._passthrough(['ostree', 'admin'] + args)
