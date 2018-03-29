import os
import sys
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
    delete_parser.add_argument("--storage", default=None, dest="storage",
                               help=_("Specify the storage from which to delete the container from. "
                                      "If not specified and there are containers with the same name in "
                                      "different storages, you will be prompted to specify."))
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
    pss.add_argument("-f", "--filter", metavar='FILTER', action='append', dest="filter",
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
    updatep.add_argument("container", nargs='?',
                         help=_("Specify one or more containers. Must be final arguments."))
    updatep.add_argument("--rebase", metavar='IMAGE', dest="rebase", default=None,
                         help=_("Rebase to a different image (useful for upgrading to a different tag)"))
    updatep.add_argument("-a", "--all", action='store_true', dest="all", default=False, help=_("Update all containers"))
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
                      "created": "created", "state": "state", "runtime": "runtime", "backend" : "backend.backend"}

    def __init__(self):
        super(Containers, self).__init__()
        self.beu = BackendUtils()

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
                it = con_obj
                for i in _filter.split("."):
                    it = getattr(it, i, None)
                if _value.lower() in it.lower():
                    _filtered.append(con_obj)
            return _filtered

        if not self.args.filter:
            return con_objs
        for f in self.args.filter:
            cfilter, value = f.split('=', 1)
            cfilter = self.FILTER_KEYWORDS[cfilter]
            con_objs = _walk(con_objs, cfilter, value)
        return con_objs

    def ps_tty(self):
        if self.args.debug:
            util.write_out(str(self.args))
            self.beu.dump_backends()


        container_objects = self._ps()
        # If we were not asked for json output, return out with no output
        # when there are no applicable container objects
        if not self.args.json:
            if len(container_objects) == 0:
                return 0

            if not any([x.running for x in container_objects]) and not self.args.all:
                return 0

        # Set to 12 when truncate
        if self.args.truncate:
            max_container_id = 12
        # Otherwise set to the max, falling back to 0
        else:
            max_container_id = max([len(x.id) for x in container_objects] or [0])

        # Quiet supersedes json output
        if self.args.quiet:
            for con_obj in container_objects:
                util.write_out(con_obj.id[0:max_container_id])
            return 0

        if self.args.json:
            util.output_json(self._to_json(container_objects))
            return 0

        max_image_name = 20 if self.args.truncate else max([len(x.image_name) for x in container_objects])
        if self.args.truncate:
            max_command = 10
        else:
            _max_command = max([len(x.command) for x in container_objects])
            max_command = _max_command if _max_command > 9 else 10

        max_container_name = 10 if self.args.truncate else max([len(x.name) for x in container_objects])

        col_out = "{0:2} {1:%s} {2:%s} {3:%s} {4:%s} {5:16} {6:10} {7:10} {8:10}" % (max_container_id,
                                                                                     max_image_name,
                                                                                     max_container_name,
                                                                                     max_command)
        if self.args.heading:
            util.write_out(col_out.format(" ",
                                          "CONTAINER ID",
                                          "IMAGE",
                                          "NAME",
                                          "COMMAND",
                                          "CREATED",
                                          "STATE",
                                          "BACKEND",
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
                                          con_obj.name[0:max_container_name],
                                          str(con_obj.command)[0:max_command],
                                          con_obj.created[0:16],
                                          con_obj.state[0:10],
                                          con_obj.backend.backend[0:10],
                                          con_obj.runtime[0:10]))

    def ps(self):
        container_objects = self._ps()
        return self._to_json(container_objects)

    def _ps(self):
        def _check_filters():
            if not self.args.filter:
                return True
            for f in self.args.filter:
                _filter, _ = f.split('=', 1)
                keywords = list(self.FILTER_KEYWORDS.keys())
                if _filter not in keywords:
                    raise ValueError("The filter {} is not valid.  "
                                     "Please choose from {}".format(_filter, keywords))
        _check_filters()
        containers = self.filter_container_objects(self.beu.get_containers())
        self._mark_vulnerable(containers)
        if self.args.all:
            return containers
        return [x for x in containers if x.running]

    @staticmethod
    def _to_json(con_objects):
        containers = []
        for con_obj in con_objects:
            _con = {'id': con_obj.id,
                    'image_id': con_obj.image,
                    'image_name': con_obj.image_name,
                    'name': con_obj.name,
                    'command': con_obj.command,
                    'created': con_obj.created,
                    'state': con_obj.state,
                    'backend': con_obj.backend.backend,
                    'runtime': con_obj.runtime,
                    'vulnerable': con_obj.vulnerable,
                    'running': con_obj.running
                    }
            containers.append(_con)
        return containers

    def delete(self):
        if self.args.debug:
            util.write_out(str(self.args))
            self.beu.dump_backends()

        if (len(self.args.containers) > 0 and self.args.all) or (len(self.args.containers) < 1 and not self.args.all):
            raise ValueError("You must select --all or provide a list of containers to delete.")

        if self.args.all:
            if self.args.storage:
                be = self.beu.get_backend_from_string(self.args.storage)
                container_objects = be.get_containers()
            else:
                container_objects = self.beu.get_containers()
        else:
            container_objects = []
            for con in self.args.containers:
                _, con_obj = self.beu.get_backend_and_container_obj(con, str_preferred_backend=self.args.storage or storage, required=True if self.args.storage else False)
                container_objects.append(con_obj)

        if len(container_objects) == 0:
            raise ValueError("No containers to delete")
        four_col = "   {0:12} {1:20} {2:25} {3:10}"
        if not self.args.assumeyes:
            util.write_out("Do you wish to delete the following containers?\n")
        else:
            util.write_out("The following containers will be deleted.\n")
        util.write_out(four_col.format("ID", "NAME", 'IMAGE_NAME', "STORAGE"))
        for con in container_objects:
            util.write_out(four_col.format(con.id[0:12], con.name[0:20], con.image_name[0:25], con.backend.backend))
        if not self.args.assumeyes:
            confirm = util.input("\nConfirm (y/N) ")
            confirm = confirm.strip().lower()
            if not confirm in ['y', 'yes']:
                util.write_err("User aborted delete operation for {}".format(self.args.containers or "all containers"))
                sys.exit(2)

        for del_con in container_objects:
            try:
                del_con.backend.delete_container(del_con.id, force=self.args.force)
            except APIError as e:
                util.write_err("Failed to delete container {}: {}".format(con.id, e))
        return 0

    def _mark_vulnerable(self, containers):
        assert isinstance(containers, list)
        vulnerable_uuids = self.get_vulnerable_ids()
        for con in containers:
            if con.id in vulnerable_uuids:
                con.vulnerable = True

    def update_all_containers(self):
        preupdate_containers = self.syscontainers.get_containers()
        could_not_update = {}
        for i in preupdate_containers:
            name = i['Names'][0]
            util.write_out("Checking container {}...".format(name))
            try:
                self.syscontainers.update_container(name, controlled=True)
            except:  # pylint: disable=bare-except
                could_not_update[name] = True

        postupdate_containers = self.syscontainers.get_containers()

        images_by_name = {i['RepoTags'][0] : i for i in self.syscontainers.get_system_images()}
        preupdate_containers_by_name = {i['Names'][0] : i for i in preupdate_containers}
        postupdate_containers_by_name = {i['Names'][0] : i for i in postupdate_containers}

        def get_image_id(c): return c['ImageId'] if 'ImageId' in c else c['ImageID']

        def colored(line, color):
            if sys.stdout.isatty():
                return "\x1b[1;%dm%s\x1b[0m" % (color, line)
            else:
                return line

        def get_status(container_name, pre_id, post_id, image_id):
            COLOR_RED = 31
            COLOR_GREEN = 32
            COLOR_YELLOW = 33

            if container_name in could_not_update:
                return "Failed", COLOR_RED
            if image_id == None:
                return "Unknown", COLOR_YELLOW
            if post_id == image_id and image_id != pre_id:
                return "Updated now", COLOR_GREEN
            if post_id == image_id and image_id == pre_id:
                return "Updated", COLOR_GREEN
            return "Not updated", COLOR_RED

        cols = "{0:15} {1:32} {2:32} {3:32} {4:15}"

        util.write_out("\nSUMMARY\n")
        util.write_out(cols.format("Container", "Image ID before update", "Image ID after update", "Latest image ID", "Status"))
        for cnt in preupdate_containers_by_name.keys():
            pre_version = get_image_id(preupdate_containers_by_name[cnt])
            post_version = get_image_id(postupdate_containers_by_name[cnt])
            img_name = img_id = None
            try:
                img_name = preupdate_containers_by_name[cnt]['Image']
                img_id = get_image_id(images_by_name[img_name])
            except KeyError:
                pass
            status, color = get_status(cnt, pre_version, post_version, img_id)
            colored_status = colored(status[:15], color)
            util.write_out(cols.format(cnt[:15], pre_version[:32], post_version[:32], (img_id or "<NOT FOUND>")[:32], colored_status))

    def update(self):
        if self.args.all:
            if self.args.container is not None:
                raise ValueError("Incompatible options specified.  --all doesn't support a container name")
            if self.args.setvalues or self.args.rebase:
                raise ValueError("Incompatible options specified.  --all doesn't support --set or --rebase")

            return self.update_all_containers()

        if self.args.container is None:
            raise ValueError("Too few arguments.  Please specify the container")

        if self.syscontainers.get_checkout(self.args.container):
            return self.syscontainers.update_container(self.args.container, self.args.setvalues, self.args.rebase)
        raise ValueError("System container '%s' is not installed" % self.args.container)

    def rollback(self):
        util.write_out("Attempting to roll back system container: %s" % self.args.container)
        self.syscontainers.rollback(self.args.container)
