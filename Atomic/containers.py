import os
import copy

from . import util
from . import Atomic
from .client import AtomicDocker
from docker.errors import APIError
from Atomic.backendutils import BackendUtils
from .syscontainers import OSTREE_PRESENT

try:
    from subprocess import DEVNULL  # pylint: disable=no-name-in-module
except ImportError:
    DEVNULL = open(os.devnull, 'wb')

ATOMIC_CONFIG = util.get_atomic_config()
storage = ATOMIC_CONFIG.get('default_storage', "docker")

def cli(subparser):
    # atomic containers
    c = subparser.add_parser("containers",
                             help=_("operate on containers"))
    containers_subparser = c.add_subparsers(title='containers subcommands',
                                            description="operate on containers",
                                            help='additional help')
    # atomic containers delete
    delete_parser = containers_subparser.add_parser("delete",
                                                help=_("delete specified containers"))
    delete_parser.add_argument("-f", "--force", action='store_true',
                               dest="force",
                               default=False,
                               help=_("Force removal of specified running containers"))
    delete_parser.add_argument("-a", "--all", action='store_true',dest="all",
                               default=False,
                               help=_("Delete all containers"))
    delete_parser.add_argument("containers", nargs='*',
                              help=_("Specify one or more containers. Must be final arguments."))
    delete_parser.set_defaults(_class=Containers, func='delete')


    # atomic containers list
    pss = containers_subparser.add_parser("list",
                                          help=_("list the containers"),
                                          epilog="By default this shows only the running containers.")
    pss.set_defaults(_class=Containers, func='ps_tty')
    pss.add_argument("-a", "--all", action='store_true',dest="all", default=False,
                     help=_("show all containers"))
    pss.add_argument("-f", "--filter", metavar='FILTER', action='append', dest="filters",
                     help=_("Filter output based on conditions given in the VARIABLE=VALUE form"))
    pss.add_argument("--json", action='store_true',dest="json", default=False,
                     help=_("print in a machine parseable form"))
    pss.add_argument("-n", "--noheading", dest="heading", default=True,
                     action="store_false",
                     help=_("do not print heading when listing the containers"))
    pss.add_argument("--no-trunc", action='store_false', dest="truncate", default=True,
                     help=_("Don't truncate output"))
    pss.add_argument("-q", "--quiet", action='store_true', dest="quiet", default=False,
                     help=_("Only display container IDs"))
    # atomic containers trim
    trimp = containers_subparser.add_parser("trim",
                                            help=_("discard unused blocks (fstrim) on running containers"),
                                            epilog="Discard unused blocks (fstrim) on rootfs of running containers.")
    trimp.set_defaults(_class=Containers, func='fstrim')

    # atomic containers update/rollback
    updatep = containers_subparser.add_parser("update",
                                              help=_("update a container"),
                                              epilog="Update the container to use a newer image.")
    updatep.set_defaults(_class=Containers, func='update')
    updatep.add_argument("container",
                         help=_("Specify one or more containers. Must be final arguments."))
    if OSTREE_PRESENT:
        updatep.add_argument("--set", dest="setvalues",
                             action='append',
                             help=_("Specify a variable in the VARIABLE=VALUE "
                                    "form for a system container"))

        rollbackp = containers_subparser.add_parser("rollback",
                                                    help=_("rollback a system container"),
                                                    epilog="Perform a rollback on a system container to a previous deployment.")
        rollbackp.add_argument("container", help=_("Specify the system container to rollback"))
        rollbackp.set_defaults(_class=Containers, func='rollback')

class Containers(Atomic):

    FILTER_KEYWORDS= {"container": "id", "image": "image_name", "command": "command",
                      "created": "created", "state": "state", "runtime": "runtime"}

    def fstrim(self):
        with AtomicDocker() as client:
            for container in client.containers():
                containerId = container["Id"]
                ret = self._inspect_container(name=containerId)
                pid = ret["State"]["Pid"]
                mp = "/proc/%d/root" % (pid)
                util.write_out("Trimming container id {0}".format(containerId[0:12]))
                util.check_call(["/usr/sbin/fstrim", "-v", mp], stdout=DEVNULL)
        return

    def filter_container_objects(self, con_objs):
        def _walk(_filter_objs, _filter, _value):
            _filtered = []
            for con_obj in _filter_objs:
                if _value.lower() in getattr(con_obj, _filter, None).lower():
                    _filtered.append(con_obj)
            return _filtered

        if not self.args.filters:
            return con_objs
        filtered_objs = copy.deepcopy(con_objs)
        for f in self.args.filters:
            cfilter, value = f.split('=', 1)
            cfilter = self.FILTER_KEYWORDS[cfilter]
            filtered_objs = _walk(filtered_objs, cfilter, value)
        return filtered_objs

    def ps_tty(self):
        if self.args.debug:
            util.write_out(str(self.args))

        container_objects = self._ps()
        if not any([x.running for x in container_objects]) and not self.args.all:
            return 0

        if self.args.quiet:
            for con_obj in container_objects:
                util.write_out(con_obj.id[:12])
            return 0
        if self.args.json:
            util.output_json(self._to_json(container_objects))
            return 0

        if len(container_objects) == 0:
            return 0

        max_container_id = 12 if self.args.truncate else max([len(x.id) for x in container_objects])
        max_image_name = 20 if self.args.truncate else max([len(x.image_name) for x in container_objects])
        max_command = 20 if self.args.truncate else max([len(x.command) for x in container_objects])
        col_out = "{0:2} {1:%s} {2:%s} {3:%s} {4:16} {5:9} {6:10}" % (max_container_id, max_image_name, max_command)
        if self.args.heading:
            util.write_out(col_out.format(" ",
                                          "CONTAINER ID",
                                          "IMAGE",
                                          "COMMAND",
                                          "CREATED",
                                          "STATE",
                                          "RUNTIME"))
        for con_obj in container_objects:
            indicator = ""
            if con_obj.vulnerable:
                if util.is_python2:
                    indicator = indicator + self.skull + " "
                else:
                    indicator = indicator + str(self.skull, "utf-8") + " "
            util.write_out(col_out.format(indicator,
                                          con_obj.id[0:max_container_id],
                                          con_obj.image_name[0:max_image_name],
                                          con_obj.command[0:max_command],
                                          con_obj.created[0:16],
                                          con_obj.state[0:9],
                                          con_obj.backend.backend[0:10]))

    def ps(self):
        container_objects = self._ps()
        return self._to_json(container_objects)

    def _ps(self):
        def _check_filters():
            if not self.args.filters:
                return True
            for f in self.args.filters:
                _filter, _ = f.split('=', 1)
                if _filter not in [x for x in self.FILTER_KEYWORDS]:
                    raise ValueError("The filter {} is not valid.  "
                                     "Please choose from {}".format(_filter, [x for x in self.FILTER_KEYWORDS]))
        _check_filters()
        beu = BackendUtils()
        containers = self.filter_container_objects(beu.get_containers())
        self._mark_vulnerable(containers)
        if self.args.all:
            return containers
        return [x for x in containers if x.running]

    @staticmethod
    def _to_json(con_objects):
        containers = []
        for con_obj in con_objects:
            _con = {'id': con_obj.id,
                    'image_id': con_obj.image_id,
                    'image_name': con_obj.image_name,
                    'command': con_obj.command,
                    'created': con_obj.created,
                    'state': con_obj.state,
                    'runtime': con_obj.runtime,
                    'vulnerable': con_obj.vulnerable,
                    'running': con_obj.running
                    }
            containers.append(_con)
        return containers

    def delete(self):
        if self.args.debug:
            util.write_out(str(self.args))

        if len(self.args.containers) > 0 and self.args.all:
            raise ValueError("You must select --all or provide a list of containers to delete.")

        beu = BackendUtils()
        if self.args.all:
            container_objects = beu.get_containers()
        else:
            container_objects = []
            for con in self.args.containers:
                _, con_obj = beu.get_backend_and_container_obj(con, str_preferred_backend=storage)
                container_objects.append(con_obj)

        four_col = "   {0:12} {1:20} {2:25} {3:10}"
        util.write_out(four_col.format("ID", "NAME", 'IMAGE_NAME', "STORAGE"))
        for con in container_objects:
            util.write_out(four_col.format(con.id[0:12], con.name[0:20], con.image_name[0:25], con.backend.backend))
        if not util.confirm_input("\nDo you wish to delete the following containers?\n"):
            util.write_out("Aborting...")
            return

        for del_con in container_objects:
            try:
                del_con.backend.delete_container(del_con.id, force=self.args.force)
            except APIError as e:
                util.write_err("Failed to delete container {}: {}".format(con.id, e))

    def _mark_vulnerable(self, containers):
        assert isinstance(containers, list)
        vulnerable_uuids = self.get_vulnerable_ids()
        for con in containers:
            if con.id in vulnerable_uuids:
                con.vulnerable = True

    def update(self):
        if self.syscontainers.get_checkout(self.args.container):
            return self.syscontainers.update_container(self.args.container)
        raise ValueError("System container '%s' is not installed" % self.args.container)

    def rollback(self):
        util.write_out("Attempting to roll back system container: %s" % self.args.container)
        self.syscontainers.rollback(self.args.container)
