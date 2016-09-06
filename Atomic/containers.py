import json
import os

from . import util
from . import Atomic
from .client import AtomicDocker
import datetime
from dateutil.parser import parse as dateparse

try:
    from subprocess import DEVNULL  # pylint: disable=no-name-in-module
except ImportError:
    DEVNULL = open(os.devnull, 'wb')

def cli(subparser):
    # atomic containers
    c = subparser.add_parser("containers")
    containers_subparser = c.add_subparsers(title='images subcommands',
                                            description="operate on images",
                                            help='additional help')
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

class Containers(Atomic):

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
    def ps_tty(self):
        all_container_info = self.ps()
        all_containers = []
        for each in all_container_info:
            if each["Type"] == "system":
                container = each["Id"]
                status = "exited"
                created = datetime.datetime.fromtimestamp(each["Created"])
                info = self.syscontainers.get_container_runtime_info(container)
                if 'status' in info:
                    status = info["status"]
                    if 'created' in info:
                        created = info['created']

                if not self.args.all and status != "running":
                    continue

                image = each['Image']
                imageId = each['ImageID']
                command = each["Command"]
                created = created.strftime("%F %H:%M") # pylint: disable=no-member
                container_info = {"type" : "system", "container" : container,
                              "image" : image, "command" : command, "image_id" : imageId,
                              "created" : created, "status" : status,
                              "runtime" : "runc", "vulnerable" : each["vulnerable"]}

                if self.args.filter:
                    if not self._filter_include_container(container_info):
                        continue
                all_containers.append(container_info)

            elif each["Type"] == "docker":
            # Collect the docker containers
                container = each["Id"]
                ret = self._inspect_container(name=container)
                status = ret["State"]["Status"]
                image = ret['Config']['Image']
                imageId = ret['Image']
                command = u' '.join(ret['Config']['Cmd']) if ret['Config']['Cmd'] else ""
                created = dateparse(ret['Created']).strftime("%F %H:%M") # pylint: disable=no-member
                container_info = {"type" : "docker", "container" : container,
                                  "image" : image, "image_id" : imageId, "command" : command,
                                  "created" : created, "status" : status,
                                  "runtime" : "Docker", "vulnerable" : each["vulnerable"]}

                if self.args.filter:
                    if not self._filter_include_container(container_info):
                        continue
                all_containers.append(container_info)

        if not all_containers:
            return

        if self.args.json:
            util.write_out(json.dumps(all_containers))
            return

        if self.args.truncate:
            max_len_container = 12
            max_len_image = 20
            max_len_command = 20
        else:
            max_len_container = max(max([len(s["container"]) for s in all_containers]), 12)
            max_len_image = max(max([len(s["image"]) for s in all_containers]), 20)
            max_len_command = max(max([len(s["command"]) for s in all_containers]), 20)

        if self.args.quiet:
            for container in all_containers:
                util.write_out(container["container"][0:max_len_container])
            return

        col_out = "{0:2} {1:%s} {2:%s} {3:%s} {4:16} {5:9} {6:10}" % (max_len_container, max_len_image, max_len_command)

        if self.args.heading:
            util.write_out(col_out.format(" ",
                                          "CONTAINER ID",
                                          "IMAGE",
                                          "COMMAND",
                                          "CREATED",
                                          "STATUS",
                                          "RUNTIME"))

        #if self.args.truncate:
        for container in all_containers:
            indicator = ""
            if container["vulnerable"]:
                if util.is_python2:
                    indicator = indicator + self.skull + " "
                else:
                    indicator = indicator + str(self.skull, "utf-8") + " "
            util.write_out(col_out.format(indicator,
                                          container["container"][0:max_len_container],
                                          container["image"][0:max_len_image],
                                          container["command"][0:max_len_command],
                                          container["created"][0:16],
                                          container["status"][0:9],
                                          container["runtime"][0:10]))
    def ps(self):
        all_containers = []
        vuln_ids = self.get_vulnerable_ids()
        all_vuln_info = json.loads(self.get_all_vulnerable_info())

        # Collect the system containers
        for i in self.syscontainers.get_system_containers():
            i["vulnerable"] = i['Id'] in vuln_ids
            if i["vulnerable"]:
                i["vuln_info"] = all_vuln_info[i['Id']]
            else:
                i["vuln_info"] = dict()
            all_containers.append(i)

        # Collect the docker containers
        for container in [x["Id"] for x in self.d.containers(all=self.args.all)]:
            ret = self._inspect_container(name=container)
            ret["Type"] = "docker"
            ret["vulnerable"] = ret["Image"] in vuln_ids
            if ret["vulnerable"]:
                ret["vuln_info"] = all_vuln_info[ret["ImageId"]]
            else:
                ret["vuln_info"] = dict()
            all_containers.append(ret)

        return all_containers

    def _filter_include_container(self, container_info):
        filterables = ["container", "image", "command", "created", "status", "runtime"]
        for j in self.args.filter:
            var, value = str(j).split("=")
            var = var.lower()

            if var == "id" or var == "containerid":
                var = "container"

            if var not in filterables: # If the filter does not exist, default to allowing all containers through
                continue

            if value not in container_info[var]:
                return False

        return True
