import json

from . import util
from . import Atomic
import subprocess
from dateutil.parser import parse as dateparse
from . import atomic
import datetime

class Ps(Atomic):
    def ps(self):
        all_containers = []

        # Collect the system containers
        for i in self.syscontainers.get_system_containers():
            container = i["Id"]

            status = "exited"
            created = datetime.datetime.fromtimestamp(i["Created"])
            try:
                inspect_stdout = util.check_output(["runc", "state", container], stderr=atomic.DEVNULL)
                ret = json.loads(inspect_stdout.decode())
                status = ret["status"]
                created = dateparse(ret['created'])
            except (subprocess.CalledProcessError):
                pass

            if not self.args.all and status != "running":
                continue

            image = i['Image']
            command = ""
            created = created.strftime("%F %H:%M") # pylint: disable=no-member
            container_info = {"type" : "systemcontainer", "container" : container,
                              "image" : image, "command" : command, "created" : created,
                              "status" : status, "runtime" : "runc"}

            if self.args.filter:
                if not self._filter_include_container(container_info):
                    continue
            all_containers.append(container_info)

        # Collect the docker containers
        for container in [x["Id"] for x in self.d.containers(all=self.args.all)]:
            ret = self._inspect_container(name=container)
            status = ret["State"]["Status"]
            image = ret['Config']['Image']
            command = u' '.join(ret['Config']['Cmd']) if ret['Config']['Cmd'] else ""
            created = dateparse(ret['Created']).strftime("%F %H:%M") # pylint: disable=no-member
            container_info = {"type" : "docker", "container" : container,
                              "image" : image, "command" : command,
                              "created" : created, "status" : status, "runtime" : "Docker"}

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

        col_out = "{0:%s} {1:%s} {2:%s} {3:16} {4:9} {5:10}" % (max_len_container, max_len_image, max_len_command)

        if self.args.heading:
            util.write_out(col_out.format("CONTAINER ID",
                                          "IMAGE",
                                          "COMMAND",
                                          "CREATED",
                                          "STATUS",
                                          "RUNTIME"))

        #if self.args.truncate:
        for container in all_containers:
            util.write_out(col_out.format(container["container"][0:max_len_container],
                                          container["image"][0:max_len_image],
                                          container["command"][0:max_len_command],
                                          container["created"][0:16],
                                          container["status"][0:9],
                                          container["runtime"][0:10]))

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
