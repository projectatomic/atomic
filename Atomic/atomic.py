import os
import sys
import pwd
import json
import time
import math
import pipes
import getpass
import argparse
import subprocess
import shutil

try:
    from subprocess import DEVNULL  # pylint: disable=no-name-in-module
except ImportError:
    DEVNULL = open(os.devnull, 'wb')

import dbus
import docker
import requests

from . import mount
from . import util
from . import satellite
from . import pulp
from .Export import export_docker
from .Import import import_docker
import re
from .client import get_docker_client
from .util import NoDockerDaemon, DockerObjectNotFound
from docker.errors import NotFound

IMAGES = []

def convert_size(size):
    if size > 0:
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = int(math.floor(math.log(size, 1000)))
        p = math.pow(1000, i)
        s = round(size/p, 2)
        if s > 0:
            return '%s %s' % (s, size_name[i])
    return '0B'


def find_repo_tag(d, id, image_name):
    def image_in_repotags(image_name, repotags):
        if image_name in repotags:
            return image_name
        for repotag in repotags:
            if repotag.startswith("{}:".format(image_name)):
                return image_name
        return None

    global IMAGES
    if len(IMAGES) == 0:
        IMAGES = d.images()
    for image in IMAGES:
        repo_tag = image_in_repotags(image_name, image['RepoTags'])
        if repo_tag is not None:
            return repo_tag
        if id == image["Id"]:
            return image["RepoTags"][0]
    return ""


class Atomic(object):
    INSTALL_ARGS = ["run",
                    "-t",
                    "-i",
                    "--rm",
                    "--privileged",
                    "-v", "/:/host",
                    "--net=host",
                    "--ipc=host",
                    "--pid=host",
                    "-e", "HOST=/host",
                    "-e", "NAME=${NAME}",
                    "-e", "IMAGE=${IMAGE}",
                    "-e", "CONFDIR=/host/etc/${NAME}",
                    "-e", "LOGDIR=/host/var/log/${NAME}",
                    "-e", "DATADIR=/host/var/lib/${NAME}",
                    "--name", "${NAME}",
                    "${IMAGE}"]

    SPC_ARGS = ["run",
                "-t",
                "-i",
                "--rm",
                "--privileged",
                "-v", "/:/host",
                "-v", "/run:/run",
                "-v", "/etc/localtime:/etc/localtime",
                "--net=host",
                "--ipc=host",
                "--pid=host",
                "-e", "HOST=/host",
                "-e", "NAME=${NAME}",
                "-e", "IMAGE=${IMAGE}",
                "${IMAGE}"]

    RUN_ARGS = ["create",
                "-t",
                "-i",
                "--name", "${NAME}",
                "${IMAGE}"]

    def __init__(self):
        self.d = get_docker_client()
        self.name = None
        self.image = None
        self.spc = False
        self.system = False
        self.inspect = None
        self.force = False
        self._images = []
        self.containers = False
        self.images_cache = []
        self.active_containers = []
        self.atomic_config = None
        self.docker_cmd = None

    def docker_binary(self):
        if not self.docker_cmd:
            self.docker_cmd = util.default_docker()
        return self.docker_cmd

    def writeOut(self, output, lf="\n"):
        sys.stdout.flush()
        sys.stdout.write(output + lf)

    def get_label(self, label, image=None):
        inspect = self._inspect_image(image)
        cfg = inspect.get("Config", None)
        if cfg:
            labels = cfg.get("Labels", [])
            if labels and label in labels:
                return labels[label]
        return ""

    def force_delete_containers(self):
        if self._inspect_image():
            image = self.image
            if self.image.find(":") == -1:
                image += ":latest"
            for c in self.get_containers():
                if c["Image"] == image:
                    self.d.remove_container(c["Id"], force=True)

    def update(self):
        self.ping()
        if self.force:
            self.force_delete_containers()
        return subprocess.check_call([self.docker_binary(), "pull", self.image])

    def pull(self):
        prevstatus = ""
        for line in self.d.pull(self.image, stream=True):
            bar = json.loads(line)
            status = bar['status']
            if prevstatus != status:
                self.writeOut(status, "")
            if 'id' not in bar:
                continue
            if status == "Downloading":
                self.writeOut(bar['progress'] + " ")
            elif status == "Extracting":
                self.writeOut("Extracting: " + bar['id'])
            elif status == "Pull complete":
                pass
            elif status.startswith("Pulling"):
                self.writeOut("Pulling: " + bar['id'])

            prevstatus = status
        self.writeOut("")

    def Export(self):
        try:
            export_docker(self.args.graph, self.args.export_location)
        except requests.exceptions.ConnectionError:
            raise NoDockerDaemon()

    def Import(self):
        self.ping()
        try:
            import_docker(self.args.graph, self.args.import_location)
        except requests.exceptions.ConnectionError:
            raise NoDockerDaemon()

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
                    self.writeOut(status, "")
                if 'id' not in bar:
                    continue
                if status == "Uploading":
                    self.writeOut(bar['progress'] + " ")
                elif status == "Push complete":
                    pass
                elif status.startswith("Pushing"):
                    self.writeOut("Pushing: " + bar['id'])

                prevstatus = status

    def set_args(self, args):
        self.args = args
        try:
            self.image = args.image
        except:
            pass
        try:
            self.command = args.command
        except:
            self.command = None

        try:
            self.spc = args.spc
        except:
            self.spc = False

        try:
            self.system = args.system
        except:
            pass

        try:
            self.name = args.name
        except:
            pass

        try:
            self.force = args.force
        except:
            pass

        if not self.name and self.image is not None:
            self.name = self.image.split("/")[-1].split(":")[0]
            if self.spc:
                self.name = self.name + "-spc"
            if self.system:
                self.name = self.name + "-system"

    def _getconfig(self, key, default=None):
        assert self.inspect is not None
        cfg = self.inspect.get("Config")
        if cfg is None:
            return default
        val = cfg.get(key, default)
        if val is None:
            return default
        return val

    def _get_cmd(self):
        return self._getconfig("Cmd", ["/bin/sh"])

    def _get_labels(self):
        return self._getconfig("Labels", [])

    def _interactive(self):
        return (self._getconfig("AttachStdin", False) and
                self._getconfig("AttachStdout", False) and
                self._getconfig("AttachStderr", False))

    def _running(self):
        if self._interactive():
            cmd = [self.docker_binary(), "exec", "-t", "-i", self.name]
            if self.command:
                cmd += self.command
            else:
                cmd += self._get_cmd()
            if self.args.display:
                return self.display(cmd)
            else:
                return subprocess.check_call(cmd, stderr=DEVNULL)
        else:
            if self.command:
                if self.args.display:
                    return self.writeOut("docker exec -t -i %s %s" %
                                         (self.name, self.command))
                else:
                    return subprocess.check_call(
                        [self.docker_binary(), "exec", "-t", "-i", self.name] +
                        self.command, stderr=DEVNULL)
            else:
                if not self.args.display:
                    self.writeOut("Container is running")

    def _start(self):
        if self._interactive():
            if self.command:
                subprocess.check_call(
                    [self.docker_binary(), "start", self.name],
                    stderr=DEVNULL)
                return subprocess.check_call(
                    [self.docker_binary(), "exec", "-t", "-i", self.name] +
                    self.command)
            else:
                return subprocess.check_call(
                    [self.docker_binary(), "start", "-i", "-a", self.name],
                    stderr=DEVNULL)
        else:
            if self.command:
                subprocess.check_call(
                    [self.docker_binary(), "start", self.name],
                    stderr=DEVNULL)
                return subprocess.check_call(
                    [self.docker_binary(), "exec", "-t", "-i", self.name] +
                    self.command)
            else:
                return subprocess.check_call(
                    [self.docker_binary(), "start", self.name],
                    stderr=DEVNULL)

    def _inspect_image(self, image=None):
        try:
            if image:
                return self.d.inspect_image(image)
            return self.d.inspect_image(self.image)
        except NotFound:
            pass
        except requests.exceptions.ConnectionError:
            raise NoDockerDaemon()

        return None

    def _inspect_container(self, name=None):
        if name is None:
            name = self.name
        try:
            return self.d.inspect_container(name)
        except NotFound:
            pass
        except requests.exceptions.ConnectionError as e:
            raise NoDockerDaemon()
        return None

    def _get_args(self, label):
        labels = self._get_labels()
        for l in [label, label.lower(), label.capitalize(), label.upper()]:
            if l in labels:
                return labels[l].split()
        return None

    def _check_latest(self):
        inspect = self._inspect_image()
        if inspect and inspect["Id"] != self.inspect["Image"]:
            sys.stdout.write(
                "The '%(name)s' container is using an older version of the "
                "installed\n'%(image)s' container image. If you wish to use "
                "the newer image,\nyou must either create a new container "
                "with a new name or\nuninstall the '%(name)s' container."
                "\n\n# atomic uninstall --name %(name)s %(image)s\n\nand "
                "create new container on the '%(image)s' image.\n\n# atomic "
                "update --force %(image)s\n\n removes all containers based on "
                "an image." % {"name": self.name, "image": self.image})

    def container_run_command(self):
        command = "%s run " % sys.argv[0]
        if self.spc:
            command += "--spc "

        if self.name != self.image:
            command += "--name %s " % self.name
        command += self.image
        return command

    #def run -> Atomic/run.py

    def stop(self):
        self.inspect = self._inspect_container()
        if self.inspect is None:
            self.inspect = self._inspect_image()
            if self.inspect is None:
                raise DockerObjectNotFound(self.name)

        args = self._get_args("STOP")
        if args:
            cmd = self.gen_cmd(args + list(map(pipes.quote, self.args.args)))
            cmd = self.sub_env_strings(cmd)
            self.display(cmd)
            util.check_call(cmd, env=self.cmd_env())

        # Container exists
        try:
            if self.inspect["State"]["Running"]:
                self.d.stop(self.name)
        except KeyError:
            pass

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

    def host_status(self):
        argv = ["status"]
        if self.args.pretty:
            argv.append("--pretty")
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

    def uninstall(self):
        if self._system_container_exists(self.name):
            return self._uninstall_system_container()

        self.inspect = self._inspect_container()
        if self.inspect and self.force:
            self.force_delete_containers()
        try:
            # Attempt to remove container, if it exists just return
            self.d.stop(self.name)
            self.d.remove_container(self.name)
        except:
            # On exception attempt to remove image
            pass

        self.inspect = self._inspect_image()
        if not self.inspect:
            raise ValueError("Image '%s' is not installed" % self.image)

        args = self._get_args("UNINSTALL")
        if args:
            cmd = self.gen_cmd(args + list(map(pipes.quote, self.args.args)))
            cmd = self.sub_env_strings(cmd)
            self.display(cmd)
            util.check_call(cmd, env=self.cmd_env())

        if self.name == self.image:
            self.writeOut("docker rmi %s" % self.image)
            subprocess.check_call([self.docker_binary(), "rmi", self.image])

    def cmd_env(self):
        os.environ['NAME'] = self.name
        os.environ['IMAGE'] = self.image

        if hasattr(self.args, 'opt1') and self.args.opt1:
            os.environ['OPT1'] = self.args.opt1

        if hasattr(self.args, 'opt2') and self.args.opt2:
            os.environ['OPT2'] = self.args.opt2

        if hasattr(self.args, 'opt3') and self.args.opt3:
            os.environ['OPT3'] = self.args.opt3

        if not hasattr(self.args, 'PWD'):
            os.environ['PWD'] = os.getcwd()

        default_uid = "0"
        with open("/proc/self/loginuid") as f:
            default_uid = f.readline()

        if "SUDO_UID" not in os.environ:
            os.environ["SUDO_UID"] = default_uid

        if 'SUDO_GID' not in os.environ:
            os.environ["SUDO_GID"] = default_uid
        return os.environ

    def gen_cmd(self, cargs):
        args = []
        for c in cargs:
            if c == "IMAGE":
                args.append(self.image)
                continue
            if c == "IMAGE=IMAGE":
                args.append("IMAGE=%s" % self.image)
                continue
            if c == "NAME=NAME":
                args.append("NAME=%s" % self.name)
                continue
            if c == "NAME":
                args.append(self.name)
                continue
            args.append(c)
        return " ".join(args)

    def get_fq_name(self, image_info):
        if len(image_info['RepoTags']) > 1:
            raise ValueError("\n{} is tagged with multiple repositories. "
                             "Please use a repository name instead.\n".format(self.image))
        else:
            return image_info['RepoTags'][0]

    def is_iid(self, input):
        for i in self.get_images():
            if i['Id'].startswith(self.image):
                return True
        return False

    def _no_such_image(self):
        raise ValueError("Could not find any image matching '{}'"
                         .format(self.args.image))

    def info(self):
        """
        Retrieve and print all LABEL information for a given image.
        """
        def _no_label():
            raise ValueError("'{}' has no label information."
                             .format(self.args.image))
        # Check if the input is an image id associated with more than one
        # repotag.  If so, error out.
        if self.is_iid(self.image):
            self.get_fq_name(self._inspect_image())
        # The input is not an image id
        else:
            try:
                iid = self._is_image(self.image)
                self.image = self.get_fq_name(self._inspect_image(iid))
            except AtomicError:
                if self.args.force_remote_info:
                    self.image = self.find_remote_image()
                if self.image is None:
                    self._no_such_image()
        util.writeOut("Image Name: {}".format(self.image))
        inspection = None
        if not self.args.force_remote_info:
            inspection = self._inspect_image(self.image)
            # No such image locally, but fall back to remote
        if inspection is None:
            # Shut up pylint in case we're on a machine with upstream
            # docker-py, which lacks the remote keyword arg.
            #pylint: disable=unexpected-keyword-arg
            inspection = util.skopeo(self.image)
            # image does not exist on any configured registry
        try:
            labels = inspection['Config']['Labels']
        except TypeError:  # pragma: no cover
            # Some images may not have a 'Labels' key.
            _no_label()
        if labels is not None and len(labels) is not 0:
            for label in labels:
                self.writeOut('{0}: {1}'.format(label, labels[label]))
        else:
            _no_label()

    def dangling(self, image):
        if image == "<none>":
            return "*"
        return " "

    def images(self):
        def get_col_lengths(_images):
            '''
            Determine the max length of the repository and tag names
            :param _images:
            :return: a set with len of repository and tag

            If there are no images, return 1, 1
            '''
            repo_tags = [item.split(":") for sublist in _images for item
                         in sublist['RepoTags']]
            # We add the 1 to the repo max length for self.dangling(repo)
            if repo_tags:
                return max([len(x[0]) for x in repo_tags]) + 1,\
                       max([len(x[1]) for x in repo_tags])
            else:
                return 1, 1

        enc = sys.getdefaultencoding()
        if self.args.prune:
            cmd = "docker images --filter dangling=true -q".split()
            for i in subprocess.check_output(cmd, stderr=DEVNULL).split():
                self.d.remove_image(i.decode(enc), force=True)
            return

        _images = self.get_images()
        if len(_images) == 0:
            return
        _max_repo, _max_tag = get_col_lengths(_images)
        col_out = "{0:" + str(_max_repo) + "} {1:" + str(_max_tag) + \
                  "} {2:12} {3:19} {4:10}"
        self.writeOut(col_out.format("REPOSITORY", "TAG", "IMAGE ID",
                                     "CREATED", "VIRTUAL SIZE"))
        for image in self.get_images():
            repo, tag = image["RepoTags"][0].rsplit(":", 1)
            self.writeOut(col_out.format(self.dangling(repo) + repo,
                                         tag, image["Id"][:12],
                 time.strftime("%F %H:%M",
                               time.localtime(image["Created"])),
                 convert_size(image["VirtualSize"])))


    def _check_if_image_present(self):
        self.inspect = self._inspect_image()
        if not self.inspect:
            if self.args.display:
                self.display("Need to pull %s" % self.image)
                return
            self.update()
            self.inspect = self._inspect_image()

    def install(self):
        if self.system:
            return self._install_system_container()

        self._check_if_image_present()
        args = self._get_args("INSTALL")
        if not args:
            return

        cmd = self.sub_env_strings(self.gen_cmd(args + list(map(pipes.quote, self.args.args))))

        self.display(cmd)

        if not self.args.display:
            return util.check_call(cmd)

    def systemctl_command(self, cmd):
        cmd = self.sub_env_strings(self.gen_cmd(["systemctl", cmd, self.image]))
        self.display(cmd)
        if not self.args.display:
            util.check_call(cmd, env=self.cmd_env())

    def _system_container_exists(self, name):
        return os.path.exists("/var/system/%s" % name)

    def _uninstall_system_container(self):
        systemdir = os.path.realpath("/var/system/%s" % self.image)
        service_installed = os.path.exists(os.path.join(systemdir, "rootfs/exports/service.template"))
        self.args.display = False
        if service_installed:
            self.systemctl_command("stop")
            self.systemctl_command("disable")

        if service_installed:
            os.unlink("/usr/local/lib/systemd/system/%s.service" % (self.image))

        exportedfs = os.path.join(systemdir, "rootfs/exports/rootfs/")
        for root, _, files in os.walk(exportedfs):
            for f in files:
                os.unlink("/" + os.path.relpath(os.path.join(root, f), exportedfs))

        os.unlink("/var/system/%s" % self.image)
        shutil.rmtree("/var/system/%s.0" % self.image)

    def _install_system_container(self):
        self._check_if_image_present()

        cmd = self.sub_env_strings(self.gen_cmd(["docker", "run", "-d", "--name", self.image, self.image]))
        self.display(cmd)
        if not self.args.display:
            util.check_call(cmd, env=self.cmd_env())

        try:
            destination = "/var/system/%s.%d" % (self.image, 0)
            rootfs = os.path.join(destination, "rootfs")
            cmd = "docker export '%s' | tar --directory='%s' -xf -" % (self.image, rootfs)
            self.display(cmd)
            if not self.args.display:
                os.makedirs(rootfs)
                subprocess.check_call(cmd, shell=True)

            exports = os.path.join(destination, "rootfs/exports")
            exportfs = os.path.join(exports, "rootfs")
            if os.path.exists(exportfs):
                shutil.copy2(exportfs, "/")

            if not self.args.display:
                sym = "/var/system/%s" % (self.image)
                if os.path.exists(sym):
                    os.unlink(sym)
                os.symlink(destination, sym)

            shutil.copy2(os.path.join(exports, "config.json"), os.path.join(destination, "config.json"))

            unitfile = os.path.join(exports, "service.template")
            unitfileout = "/usr/local/lib/systemd/system/%s.service" % (self.image)
            if os.path.exists(unitfile):
                with open(unitfile, 'r') as infile, open(unitfileout, "w") as outfile:
                    outfile.write(infile.read().replace("$DEST", destination))

        finally:
            cmd = self.sub_env_strings(self.gen_cmd(["docker", "rm", "-f", self.image]))
            self.writeOut(cmd)
            if not self.args.display:
                util.check_call(cmd, env=self.cmd_env())


    def help(self):
        if os.path.exists("/usr/bin/rpm-ostree"):
            return _('Atomic Management Tool')
        else:
            return _('Atomic Container Tool')

    def print_spc(self):
        return "%s %s" % (self.docker_binary(), " ".join(self.SPC_ARGS))

    def print_run(self):
        return "%s %s" % (self.docker_binary(), " ".join(self.RUN_ARGS))

    def print_install(self):
        return "%s %s %s" % (self.docker_binary(), " ".join(self.INSTALL_ARGS), "/usr/bin/INSTALLCMD")

    def print_uninstall(self):
        return "%s %s %s" % (self.docker_binary(), " ".join(self.INSTALL_ARGS), "/usr/bin/UNINSTALLCMD")

    def _get_layer(self, image):
        def get_label(label):
            return self.get_label(label, image["Id"])
        image = self._inspect_image(image)
        if not image:
            raise ValueError("Image '%s' does not exist" % self.image)
        version = ("%s-%s-%s" % (get_label("Name"), get_label("Version"),
                                 get_label("Release"))).strip("-")
        return({"Id": image['Id'], "Name": get_label("Name"),
                "Version": version, "Tag": find_repo_tag(self.d, image['Id'], self.image),
                "Parent": image['Parent']})

    def get_layers(self):
        layers = []
        layer = self._get_layer(self.image)
        layers.append(layer)
        while layer["Parent"] != "":
            layer = self._get_layer(layer["Parent"])
            layers.append(layer)
        return layers

    def _get_all_image_ids(self):
        iids = []
        for image in self.get_images():
            iids.append(image['Id'])
        return iids

    def _get_all_container_ids(self):
        cids = []
        for con in self.get_containers():
            cids.append(con['Id'])
        return cids

    def _get_image_infos(self, image):
        def get_label(label):
            return self.get_label(label, image["Id"])

        return {"Id": image['Id'], "Name": get_label("Name"),
                "Version": ("%s-%s-%s" % (get_label("Name"),
                                          get_label("Version"),
                                          get_label("Release"))).strip(":"),
                "Tag": image["RepoTags"][0]}

    def get_image_infos(self):
        if len(self._images) > 0:
            return self._images

        images = self.get_images()
        for image in images:
            self._images.append(self._get_image_infos(image))

        return self._images


    def mount(self, mountpoint=None, image=None, live=False):
        try:
            if mountpoint is None:
                mountpoint = self.args.mountpoint
            if image is None:
                image = self.args.image
            if 'live' in self.args:
                live = self.args.live

            options = [opt for opt in self.args.options.split(',') if opt] if 'options' in self.args else ""
            mount.DockerMount(mountpoint, live).mount(image, options)

            # only need to bind-mount on the devicemapper driver
            if self.d.info()['Driver'] == 'devicemapper':
                mount.Mount.mount_path(os.path.join(mountpoint, "rootfs"),
                                       mountpoint,
                                       bind=True)

        except (mount.MountError, mount.NoDockerDaemon) as dme:
            raise ValueError(str(dme))

    def unmount(self, mountpoint=None):
        if mountpoint is None:
            mountpoint = self.args.mountpoint
        try:
            dev = mount.Mount.get_dev_at_mountpoint(mountpoint)

            # If there's a bind-mount over the directory, unbind it.
            if dev.rsplit('[', 1)[-1].strip(']') == '/rootfs' \
                    and self.d.info()['Driver'] == 'devicemapper':
                mount.Mount.unmount_path(mountpoint)

            return mount.DockerMount(mountpoint).unmount()

        except mount.MountError as dme:
            raise ValueError(str(dme))

    def version(self):
        def get_label(label):
            val = self._get_args(label)
            if val:
                return val[0]
            return ""

        try:
            self.inspect = self.d.inspect_image(self.image)
        except NotFound:
            self.update()
            self.inspect = self.d.inspect_image(self.image)
        except requests.exceptions.ConnectionError:
            raise NoDockerDaemon()
        if self.args.recurse:
            return self.get_layers()
        else:
            return [self._get_layer(self.image)]

    def print_version(self):
        for layer in self.version():
            version = layer["Version"]
            if layer["Version"] == '':
                version = "None"
            self.writeOut("%s %s %s" % (layer["Id"], version, layer["Tag"]))

    def display(self, cmd):
        util.writeOut(self.sub_env_strings(cmd))

    def sub_env_strings(self, in_string):
        """
        Performs substitutions on an input string based on defined
        environment variables.
        :param in_string: string to perform the subs on
        :return: string
        """
        # Set environment variables
        self.cmd_env()

        # Perform variable subs
        in_string = os.path.expandvars(in_string)

        # Replace undefined variables with blank
        in_string = re.sub('\$\{?\S*\}?', '', in_string)

        # Solve whitespacing
        in_string = " ".join(in_string.split())

        return in_string

    def ping(self):
        '''
        Check if the docker daemon is running; if not, exit with
        message and return code 1
        '''
        try:
            self.d.ping()
        except requests.exceptions.ConnectionError:
            raise NoDockerDaemon()

    def _is_container(self, identifier, active=False):
        '''
        Checks is the identifier is a container ID or container name.  If
        it is, returns the full container ID. Else it will return an
        AtomicError.  Takes optional keyword active, which signifies
        that you want to only deal with active containers.
        '''
        if active:
            active_cons = self.get_active_containers()
            active_con_ids = [x['Id'] for x in active_cons]
            cons = active_cons
        else:
            cons = self.get_containers()

        # First check if the container exists by whatever
        # identifier was given
        self.inspect = self._inspect_container(name=identifier)
        if self.inspect is not None:
            # Inspect found a match
            if not active:
                return self.inspect['Id']
            else:
                # Check if the container is active
                if self.inspect['Id'] in active_con_ids:
                    return self.inspect['Id']

        err_append = "Refine your search to narrow results."

        # The identifier might be a partial name?
        con_ids = []
        for con in cons:
            for name in con['Names']:
                if name.startswith("/{0}".format(identifier)):
                    con_ids.append(con['Id'])
                    break

        # More than one match was found
        if len(con_ids) > 1:
            raise AtomicError("Multiple matches were found for {0}. {1}"
                              .format(identifier, err_append))
        # No matches were found
        elif len(con_ids) < 1:
            active_err = '' if not active else 'active '
            error_msg = "Unable to find {0}container '{1}'".format(active_err,
                                                                   identifier)
            raise AtomicError(error_msg)
        else:
            self.inspect = self._inspect_container(con_ids[0])
            return con_ids[0]

    def _is_image(self, identifier):
        '''
        Checks is the identifier is a image ID or a matches an image name.
        If it finds a match, it returns the full image ID. Else it will
        return an AtomicError.
        '''
        err_append = "Refine your search to narrow results."
        image_info = self.get_images()

        inspect = self._inspect_image(image=identifier)

        if inspect is not None:
            self.inspect = inspect
            return inspect['Id']

        name_search = util.image_by_name(identifier, images=image_info)
        if len(name_search) > 0:
            if len(name_search) > 1:
                tmp_image = dict((x['Id'], x['RepoTags']) for x in image_info)
                repo_tags = []
                for name in name_search:
                    for repo_tag in tmp_image.get(name['Id']):
                        if repo_tag.find(identifier) > -1:
                            repo_tags.append(repo_tag)
                raise ValueError("Found more than one image possibly "
                                 "matching '{0}'. They are:\n    {1} \n{2}"
                                 .format(identifier, "\n    ".join(repo_tags),
                                         err_append))
            return name_search[0]['Id']
        # No dice
        raise AtomicError

    def get_input_id(self, identifier):
        '''
        Determine if the input "identifier" is valid.  Return the container or
        image ID when true and raise a ValueError when not
        '''
        try:
            return self._is_image(identifier)
        except AtomicError:
            pass
        try:
            return self._is_container(identifier)
        except AtomicError:
            pass
        raise DockerObjectNotFound(identifier)

    def get_images(self):
        '''
        Wrapper function that should be used instead of querying docker
        multiple times for a list of images.
        '''
        if len(self.images_cache) == 0:
            try:
                images = self.d.images()
            except requests.exceptions.ConnectionError:
                raise NoDockerDaemon()
            if images:
                self.images_cache = images
        return self.images_cache

    def get_containers(self):
        '''
        Wrapper function that should be used instead of querying docker
        multiple times for a list of containers
        '''
        if not self.containers:
            self.containers = self.d.containers(all=True)

        return self.containers

    def get_active_containers(self, refresh=False):
        '''
        Wrapper function for obtaining active containers.  Should be used
        instead of direct queries to docker
        '''
        if len(self.active_containers) == 0 or refresh:
            self.active_containers = self.d.containers(all=False)

        return self.active_containers

    def find_remote_image(self):
        """
        Based on the user's input, see if we can associate the input with a remote
        registry and image.
        :return: str(fq name)
        """
        results = self.d.search(self.image)
        for x in results:
            if x['name'] == self.image:
                return '{}/{}'.format(x['registry_name'], x['name'])
        return None

    def get_atomic_config_item(self, config_items):
        """
        Lookup and return the atomic configuration file value
        for a given structure. Returns None if the option
        cannot be found.
        """
        def _recursive_get(items):
            yaml_struct = self.atomic_config
            try:
                for i in items:
                    yaml_struct = yaml_struct[i]
            except KeyError:
                return None
            return yaml_struct
        if self.atomic_config is None:
            self.atomic_config = util.get_atomic_config()
        return _recursive_get(config_items)

class AtomicError(Exception):
    pass

def SetFunc(function):
    class customAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            setattr(namespace, self.dest, function)
    return customAction
