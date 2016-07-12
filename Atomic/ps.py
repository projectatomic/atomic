import json

from . import util
from . import Atomic
from dateutil.parser import parse as dateparse

class Ps(Atomic):
    def ps(self):
        all_containers = []

        # Collect the system containers
        for i in self.syscontainers.get_system_containers():
            container = i["Id"]
            inspect_stdout = util.check_output(["runc", "state", container])
            ret = json.loads(inspect_stdout)
            status = ret["status"]
            if not self.args.all and status != "running":
                continue

            image = i['Image']
            command = ""
            created = dateparse(ret['created']).strftime("%F %H:%M") # pylint: disable=no-member
            all_containers.append({"type" : "systemcontainer", "container" : container,
                                   "image" : image, "command" : command, "created" : created,
                                   "status" : status})

        # Collect the docker containers
        for container in [x["Id"] for x in self.d.containers(all=self.args.all)]:
            ret = self._inspect_container(name=container)
            status = ret["State"]["Status"]
            image = ret['Config']['Image']
            command = u' '.join(ret['Config']['Cmd']) if ret['Config']['Cmd'] else ""
            created = dateparse(ret['Created']).strftime("%F %H:%M") # pylint: disable=no-member
            all_containers.append({"type" : "docker", "container" : container,
                                   "image" : image, "command" : command,
                                   "created" : created, "status" : status})

        if self.args.json:
            self.write_out(json.dumps(all_containers))
            return

        col_out = "{0:12} {1:20} {2:20} {3:15} {4:9}"
        if self.args.heading:
            self.write_out(col_out.format("CONTAINER ID",
                                          "IMAGE",
                                          "COMMAND",
                                          "CREATED",
                                          "STATUS"))

        for container in all_containers:
            self.write_out(col_out.format(container["container"][0:12],
                                          container["image"][0:20],
                                          container["command"][0:20].encode('utf-8'),
                                          container["created"][0:15],
                                          container["status"][0:9]))
