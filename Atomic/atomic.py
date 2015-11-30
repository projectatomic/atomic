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
import dbus

try:
    from subprocess import DEVNULL  # pylint: disable=no-name-in-module
except ImportError:
    DEVNULL = open(os.devnull, 'wb')

import dbus
import docker
import requests

from . import diff
from . import mount
from . import util
from . import satellite
from . import pulp
from .Export import export_docker
from .Import import import_docker


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


def find_repo_tag(d, id):
    global IMAGES
    if len(IMAGES) == 0:
        IMAGES = d.images()
    for image in IMAGES:
        if id == image["Id"]:
            return image["RepoTags"][0]
    return ""


class Atomic(object):
    INSTALL_ARGS = ["/usr/bin/docker", "run",
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

    SPC_ARGS = ["/usr/bin/docker", "run",
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

    RUN_ARGS = ["/usr/bin/docker", "create",
                "-t",
                "-i",
                "--name", "${NAME}",
                "${IMAGE}"]

    def __init__(self):
        self.d = docker.Client()
        self.name = None
        self.image = None
        self.spc = False
        self.inspect = None
        self.force = False
        self._images = []
        self.containers = False
        self.images_cache = None
        self.active_containers = False

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
        if self.force:
            self.force_delete_containers()
        return subprocess.check_call(["/usr/bin/docker", "pull", self.image])

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
        export_docker(self.args.graph, self.args.export_location)

    def Import(self):
        import_docker(self.args.graph, self.args.import_location)

    def push(self):
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
            cmd = ["/usr/bin/docker", "exec", "-t", "-i", self.name]
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
                    return self.writeOut("/usr/bin/docker exec -t -i %s %s" %
                                         (self.name, self.command))
                else:
                    return subprocess.check_call(
                        ["/usr/bin/docker", "exec", "-t", "-i", self.name] +
                        self.command, stderr=DEVNULL)
            else:
                if not self.args.display:
                    self.writeOut("Container is running")

    def _start(self):
        if self._interactive():
            if self.command:
                subprocess.check_call(
                    ["/usr/bin/docker", "start", self.name],
                    stderr=DEVNULL)
                return subprocess.check_call(
                    ["/usr/bin/docker", "exec", "-t", "-i", self.name] +
                    self.command)
            else:
                return subprocess.check_call(
                    ["/usr/bin/docker", "start", "-i", "-a", self.name],
                    stderr=DEVNULL)
        else:
            if self.command:
                subprocess.check_call(
                    ["/usr/bin/docker", "start", self.name],
                    stderr=DEVNULL)
                return subprocess.check_call(
                    ["/usr/bin/docker", "exec", "-t", "-i", self.name] +
                    self.command)
            else:
                return subprocess.check_call(
                    ["/usr/bin/docker", "start", self.name],
                    stderr=DEVNULL)

    def _inspect_image(self, image=None):
        try:
            if image:
                return self.d.inspect_image(image)
            return self.d.inspect_image(self.image)
        except docker.errors.APIError:
            pass
        except requests.exceptions.ConnectionError as e:
            raise IOError("Cannot connect to the Docker daemon. Is the docker daemon running on this host?")

        return None

    def _inspect_container(self, name=None):
        if name is None:
            name = self.name
        try:
            return self.d.inspect_container(name)
        except docker.errors.APIError:
            pass
        except requests.exceptions.ConnectionError as e:
            raise IOError("Unable to communicate with docker daemon: %s\n" %
                          str(e))
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

    def run(self):
        missing_RUN = False
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

        if self.spc:
            if self.command:
                args = self.SPC_ARGS + self.command
            else:
                args = self.SPC_ARGS + self._get_cmd()

            cmd = self.gen_cmd(args)
        else:
            args = self._get_args("RUN")
            if args:
                args += self.command
            else:
                missing_RUN = True
                if self.command:
                    args = self.RUN_ARGS + self.command
                else:
                    args = self.RUN_ARGS + self._get_cmd()

            cmd = self.gen_cmd(args)
            self.display(cmd)
            if self.args.display:
                return

            if missing_RUN:
                subprocess.check_call(cmd, env=self.cmd_env,
                                      shell=True, stderr=DEVNULL,
                                      stdout=DEVNULL)
                return self._start()

        self.display(cmd)
        if not self.args.display:
            subprocess.check_call(cmd, env=self.cmd_env, shell=True)

    def scan(self):
        if (not self.args.images and not self.args.containers and not self.args.all) and len(self.args.scan_targets) == 0:
            sys.stderr.write("\nYou must provide a list of containers or images to scan\n")
            sys.exit(1)
        self.ping()
        BUS_NAME = "org.OpenSCAP.daemon"
        OBJECT_PATH = "/OpenSCAP/daemon"
        INTERFACE = "org.OpenSCAP.daemon.Interface"
        input_resolve = {}
        if self.args.images:
            scan_list = self._get_all_image_ids()
        elif self.args.containers:
            scan_list = self._get_all_container_ids()
        elif self.args.all:
            cids = self._get_all_container_ids()
            iids = self._get_all_image_ids()
            scan_list = cids + iids
        else:
            scan_list = []
            for scan_input in self.args.scan_targets:
                docker_id = self.get_input_id(scan_input)
                input_resolve[docker_id] = scan_input
                scan_list.append(docker_id)

        # Check to make sure none of the docker objects we need to
        # scan are already mounted.
        for docker_obj in scan_list:
            if util.is_dock_obj_mounted(docker_obj):
                sys.stderr.write("\nThe object {0} is already mounted (in  "
                                 "use) and therefore cannot be scanned.\n"
                                 .format(docker_obj))
                sys.exit(1)
        bus = dbus.SystemBus()
        try:
            oscap_d = bus.get_object(BUS_NAME, OBJECT_PATH)
            oscap_i = dbus.Interface(oscap_d, INTERFACE)
            # Check if the user has asked to override the behaviour of fetching the
            # latest CVE input data, as defined in the openscap-daemon conf file
            # oscap-daemon a byte of 0 (False), 1 (True), and 2 (no change)

            if self.args.fetch_cves is None:
                fetch = 2
            elif self.args.fetch_cves:
                fetch = 1
            else:
                fetch = 0
            scan_return = json.loads(oscap_i.scan_list(scan_list, 4, fetch, timeout=99999))

        except dbus.exceptions.DBusException as e:
            message = "The openscap-daemon returned: {0}".format(e.get_dbus_message())
            if e.get_dbus_name() == 'org.freedesktop.DBus.Error.ServiceUnknown':
                message = "Unable to find the openscap-daemon dbus service. "\
                          "Either start the openscap-daemon service or pull " \
                          "and run the openscap-daemon image"
            sys.stderr.write("\n{0}\n\n".format(message))
            sys.exit(1)

        if self.args.json:
            util.output_json(scan_return)

        else:
            if not self.args.detail:
                clean = util.print_scan_summary(scan_return, input_resolve)
            else:
                clean = util.print_detail_scan_summary(scan_return,
                                                       input_resolve)
            if not clean:
                sys.exit(1)

    def stop(self):
        try:
            cid = self._is_container(self.name, active=True)
            self.name = cid
        except AtomicError as error:
            util.writeOut(error)
            sys.exit(1)

        args = self._get_args("STOP")
        if args:
            cmd = self.gen_cmd(args)
            self.display(cmd)
            subprocess.check_call(cmd, env=self.cmd_env, shell=True)

        # Container exists
        try:
            if self.inspect["State"]["Running"]:
                self.d.stop(self.name)
        except KeyError:
            pass

    def _rpmostree(self, args):
        aargs = self.args.args
        if len(aargs) > 0 and aargs[0] == "--":
            aargs = aargs[1:]
        os.execl("/usr/bin/rpm-ostree", "rpm-ostree", *(args + aargs))

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

    def uninstall(self):
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
            self.display(cmd)
            subprocess.check_call(cmd, env=self.cmd_env, shell=True)

        if self.name == self.image:
            self.writeOut("/usr/bin/docker rmi %s" % self.image)
            subprocess.check_call(["/usr/bin/docker", "rmi", self.image])

    @property
    def cmd_env(self):
        env = dict(os.environ)
        env.update({'NAME': self.name,
                    'IMAGE': self.image})

        if hasattr(self.args, 'opt1') and self.args.opt1:
            env['OPT1'] = self.args.opt1

        if hasattr(self.args, 'opt2') and self.args.opt2:
            env['OPT2'] = self.args.opt2

        if hasattr(self.args, 'opt3') and self.args.opt3:
            env['OPT3'] = self.args.opt3

        default_uid = "0"
        with open("/proc/self/loginuid") as f:
            default_uid = f.readline()

        if "SUDO_UID" in os.environ:
            env["SUDO_UID"] = os.environ["SUDO_UID"]
        else:
            env["SUDO_UID"] = default_uid

        if 'SUDO_GID' in os.environ:
            env['SUDO_GID'] = os.environ['SUDO_GID']
        else:
            try:
                env['SUDO_GID'] = str(pwd.getpwuid(int(env["SUDO_UID"]))[3])
            except:
                env["SUDO_GID"] = default_uid

        return env

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

    def info(self):
        """
        Retrieve and print all LABEL information for a given image.
        """
        def _no_such_image():
            raise ValueError('Could not find any image matching "{}".'
                             ''.format(self.args.image))

        inspection = None
        if not self.args.force_remote_info:
            try:
                inspection = self._inspect_image(self.args.image)
            except docker.errors.APIError:
                # No such image locally, but fall back to remote
                pass
        if inspection is None:
            try:
                # Shut up pylint in case we're on a machine with upstream
                # docker-py, which lacks the remote keyword arg.
                #pylint: disable=unexpected-keyword-arg
                inspection = self.d.inspect_image(self.args.image, remote=True)
            except docker.errors.APIError:
                # image does not exist on any configured registry
                _no_such_image()
            except TypeError:  # pragma: no cover
                # If a user doesn't have remote-inspection, setting remote=True
                # above will raise TypeError.
                # TODO: remove if remote inspection is accepted into docker
                # But we should error if the user specifically requested remote
                if self.args.force_remote_info:
                    raise ValueError('Your docker daemon does not support '
                                     'remote inspection.')
                else:
                    _no_such_image()
        # By this point, inspection cannot be "None"
        try:
            labels = inspection['Config']['Labels']
        except TypeError:  # pragma: no cover
            # Some images may not have a 'Labels' key.
            raise ValueError('{} has no label information.'
                             ''.format(self.args.image))
        if labels is not None:
            for label in labels:
                self.writeOut('{0}: {1}'.format(label, labels[label]))

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
            '''
            repo_tags = [item.split(":") for sublist in _images for item
                         in sublist['RepoTags']]
            # We add the 1 to the repo max length for self.dangling(repo)
            return max([len(x[0]) for x in repo_tags]) + 1,\
                   max([len(x[1]) for x in repo_tags])

        if self.args.prune:
            cmd = "/usr/bin/docker images --filter dangling=true -q".split()
            for i in subprocess.check_output(cmd, stderr=DEVNULL).split():
                self.d.remove_image(i, force=True)
            return

        _images = self.get_images()
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

    def install(self):
        self.inspect = self._inspect_image()
        if not self.inspect:
            if self.args.display:
                self.display("Need to pull %s" % self.image)
                return
            self.update()
            self.inspect = self._inspect_image()

        args = self._get_args("INSTALL")
        if not args:
            return

        cmd = self.gen_cmd(args + list(map(pipes.quote, self.args.args)))

        self.display(cmd)
        if not self.args.display:
            return subprocess.check_call(cmd, env=self.cmd_env, shell=True)

    def help(self):
        if os.path.exists("/usr/bin/rpm-ostree"):
            return _('Atomic Management Tool')
        else:
            return _('Atomic Container Tool')

    def print_spc(self):
        return " ".join(self.SPC_ARGS)

    def print_run(self):
        return " ".join(self.RUN_ARGS)

    def print_install(self):
        return " ".join(self.INSTALL_ARGS) + " /usr/bin/INSTALLCMD"

    def print_uninstall(self):
        return " ".join(self.INSTALL_ARGS) + " /usr/bin/UNINSTALLCMD"

    def _get_layer(self, image):
        def get_label(label):
            return self.get_label(label, image["Id"])
        image = self._inspect_image(image)
        if not image:
            raise ValueError("Image '%s' does not exist" % self.image)
        version = ("%s-%s-%s" % (get_label("Name"), get_label("Version"),
                                 get_label("Release"))).strip("-")
        return({"Id": image['Id'], "Name": get_label("Name"),
                "Version": version, "Tag": find_repo_tag(self.d, image['Id']),
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

    def verify(self):
        def get_label(label):
            val = self._get_args(label)
            if val:
                return val[0]
            return ""
        self.inspect = self._inspect_image()
        if not self.inspect:
            raise ValueError("Image %s does not exist" % self.image)
        current_name = get_label("Name")
        version = ""
        if current_name:
            version = "%s-%s-%s" % (current_name, get_label("Version"),
                                    get_label("Release"))

        name = None
        buf = ""
        for layer in self.get_layers():
            if name == layer["Name"]:
                continue
            name = layer["Name"]
            if len(name) > 0:
                for i in self.get_image_infos():
                    if i["Name"] == name:
                        if i["Version"] > layer["Version"]:
                            buf = ("Image '%s' contains a layer '%s' that is "
                                   "out of date.\nImage version '%s' is "
                                   "available, current version could contain "
                                   "vulnerabilities." % (self.image,
                                                         layer["Version"],
                                                         i["Version"]))
                            buf += ("You should rebuild the '%s' image using "
                                    "docker build." % (self.image))
                            break
        return buf

    def print_verify(self):
        self.writeOut(self.verify())

    def mount(self):
        try:
            options = [opt for opt in self.args.options.split(',') if opt]
            mount.DockerMount(self.args.mountpoint,
                              self.args.live).mount(self.args.image, options)

            # only need to bind-mount on the devicemapper driver
            if self.d.info()['Driver'] == 'devicemapper':
                mount.Mount.mount_path(os.path.join(self.args.mountpoint,
                                                    "rootfs"),
                                       self.args.mountpoint, bind=True)

        except mount.MountError as dme:
            raise ValueError(str(dme))

    def unmount(self):
        try:
            dev = mount.Mount.get_dev_at_mountpoint(self.args.mountpoint)

            # If there's a bind-mount over the directory, unbind it.
            if dev.rsplit('[', 1)[-1].strip(']') == '/rootfs' \
                    and self.d.info()['Driver'] == 'devicemapper':
                mount.Mount.unmount_path(self.args.mountpoint)

            return mount.DockerMount(self.args.mountpoint).unmount()

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
        except docker.errors.APIError:
            self.update()
            self.inspect = self.d.inspect_image(self.image)

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
        subprocess.check_call(
            "/bin/echo \"" + cmd + "\"", env=self.cmd_env, shell=True)

    def ping(self):
        '''
        Check if the docker daemon is running; if not, exit with
        message and return code 1
        '''
        try:
            self.d.ping()
        except requests.exceptions.ConnectionError:
            sys.stderr.write("\nUnable to communicate with docker daemon\n")
            sys.exit(1)

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
        raise ValueError("Unable to associate '{0}' with a container or image."
                         .format(identifier))

    def get_images(self):
        '''
        Wrapper function that should be used instead of querying docker
        multiple times for a list of images.
        '''
        if not self.images_cache:
            self.images_cache = self.d.images()
        return self.images_cache

    def get_containers(self):
        '''
        Wrapper function that should be used instead of querying docker
        multiple times for a list of containers
        '''
        if not self.containers:
            self.containers = self.d.containers(all=True)

        return self.containers

    def get_active_containers(self):
        '''
        Wrapper function for obtaining active containers.  Should be used
        instead of direct queries to docker
        '''
        if not self.active_containers:
            self.active_containers = self.d.containers(all=False)

        return self.active_containers


    def diff(self):
        '''
        Allows you to 'diff' the RPMs between two different docker images|containers.
        :return: None
        '''
        helpers = diff.DiffHelpers(self.args)
        images = self.args.compares
        # Check to make sure each input is valid
        for image in images:
            self.get_input_id(image)

        image_list = helpers.create_image_list(images)

        try:
            # Set up RPM classes and make sure each docker object
            # is RPM-based
            if self.args.rpms:
                rpm_image_list = helpers.build_rpm_list(image_list)

            if not self.args.no_files:
                helpers.output_files(images, image_list)

            if self.args.rpms:
                helpers.output_rpms(rpm_image_list)
        finally:
            # Clean up
            helpers._cleanup(image_list)

        if self.args.json:
            util.output_json(helpers.json_out)


class AtomicError(Exception):
    pass


def SetFunc(function):
    class customAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            setattr(namespace, self.dest, function)
    return customAction
