import sys, os
import argparse
import gettext
import docker
import json
import subprocess
import getpass
import requests
import pipes
import mount
import selinux
import util
try:
    from subprocess import DEVNULL # pylint: disable=no-name-in-module
except ImportError:
    import os
    DEVNULL = open(os.devnull, 'wb')

images=[]
def findRepoTag(d, id):
    global images
    if len(images) == 0:
        images = d.images()
    for image in images:
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
                    "-v", "${CONFDIR}:/etc/${NAME}",
                    "-v", "${LOGDIR}:/var/log/${NAME}",
                    "-v", "${DATADIR}:/var/lib/${NAME}",
                    "-e", "CONFDIR=${CONFDIR}",
                    "-e", "LOGDIR=${LOGDIR}",
                    "-e", "DATADIR=${DATADIR}",
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
                "${IMAGE}" ]

    RUN_ARGS = ["/usr/bin/docker", "create",
                "-t",
                "-i",
                "--name", "${NAME}",
                "${IMAGE}" ]

    def __init__(self):
        self.d = docker.Client()
        self.name = None
        self.image = None
        self.spc = False
        self.inspect = None
        self.force = False
        self.images = []

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
            for c in self.d.containers(all=True):
                if c["Image"] == image:
                    self.d.remove_container(c["Id"], force=True)

    def update(self):
        if self.force:
            self.force_delete_containers()
        return subprocess.check_call(["/usr/bin/docker", "pull", self.image])

    def pull(self):
        prevstatus = ""
        prev = ""
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

    def upload(self):
        prevstatus = ""
        if not self.args.username:
            self.args.username = raw_input("Registry Username: ")
        if not self.args.password:
            self.args.password = getpass.getpass("Registry Password: ")

        if self.args.pulp:
            return push_image_to_pulp(self.image, self.args.url, self.args.username, self.args.password, self.args.verify_ssl, self.d)
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
        self.args=args
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
        return self._getconfig("Cmd", [ "/bin/sh" ])

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
            return subprocess.check_call(cmd, stderr=DEVNULL)
        else:
            if self.command:
                return subprocess.check_call(["/usr/bin/docker", "exec", "-t", "-i", self.name] + self.command,
                                             stderr=DEVNULL)
            else:
                self.writeOut("Container is running")

    def _start(self):
        if self._interactive():
            if self.command:
                subprocess.check_call(["/usr/bin/docker", "start", self.name], stderr=DEVNULL)
                return subprocess.check_call(["/usr/bin/docker", "exec", "-t", "-i", self.name] + self.command)
            else:
                return subprocess.check_call(["/usr/bin/docker", "start", "-i", "-a", self.name], stderr=DEVNULL)
        else:
            if self.command:
                subprocess.check_call(["/usr/bin/docker", "start", self.name], stderr=DEVNULL)
                return subprocess.check_call(["/usr/bin/docker", "exec", "-t", "-i", self.name] + self.command)
            else:
                return subprocess.check_call(["/usr/bin/docker", "start", self.name], stderr=DEVNULL)

    def _inspect_image(self, image=None):
        try:
            if image:
                return self.d.inspect_image(image)
            return self.d.inspect_image(self.image)
        except docker.errors.APIError:
            pass
        except requests.exceptions.ConnectionError as e:
            raise IOError("Unable to communicate with docker daemon: %s\n" % str(e))
        return None

    def _inspect_container(self):
        try:
            return self.d.inspect_container(self.name)
        except docker.errors.APIError:
            pass
        except requests.exceptions.ConnectionError as e:
            raise IOError("Unable to communicate with docker daemon: %s\n" % str(e))
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
            response = ""
            sys.stdout.write("""The '%(name)s' container is using an older version of the installed
'%(image)s' container image. If you wish to use the newer image,
you must either create a new container with a new name or
uninstall the '%(name)s' container.

# atomic uninstall --name %(name)s %(image)s

and create new container on the '%(image)s' image.

atomic update --force %(image)s

removes all containers based on an image.

""" % { "name" : self.name, "image" : self.image} )

    def container_run_command(self):
        command = "%s run " % sys.argv[0]
        if self.spc:
            command += "--spc "

        if self.name != self.image:
            command += "--name %s " % self.name
        command += self.image
        return command

    def run(self):
        self.inspect = self._inspect_container()

        if self.inspect:
            self._check_latest()
            # Container exists
            if self.inspect["State"]["Running"]:
                return self._running()
            else:
                return self._start()
        else:
            if self.command:
                raise ValueError("Container '%s' must be running before executing a command into it.\nExecute the following to create the container:\n%s" % (self.name, self.container_run_command()))

        # Container does not exist
        self.inspect = self._inspect_image()
        if not self.inspect:
            self.update()
            self.inspect = self._inspect_image()

        if self.spc:
            if self.command:
                args = self.SPC_ARGS + self.command
            else:
                args = self.SPC_ARGS +  self._get_cmd()

            cmd = self.gen_cmd(args)
            self.writeOut(cmd)
        else:
            missing_RUN = False
            args = self._get_args("RUN")
            if not args:
                missing_RUN = True
                args = self.RUN_ARGS + self._get_cmd()

            cmd = self.gen_cmd(args)
            self.writeOut(cmd)

            if missing_RUN:
                subprocess.check_call(cmd, env=self.cmd_env,
                                      shell=True, stderr=DEVNULL,
                                      stdout=DEVNULL)
                return self._start()

        subprocess.check_call(cmd, env=self.cmd_env, shell=True)


    def stop(self):
        self.inspect = self._inspect_container()
        if self.inspect is None:
            self.inspect = self._inspect_image()
            if self.inspect is None:
                raise ValueError("Container/Image '%s' does not exists" % self.name)

        args = self._get_args("STOP")
        if args:
            cmd = self.gen_cmd(args)
            self.writeOut(cmd)

            subprocess.check_call(cmd, env=self.cmd_env, shell=True)


        # Container exists
        try:
            if self.inspect["State"]["Running"]:
                self.d.stop(self.name)
        except KeyError:
            pass

    def _rpmostree(self, *args):
        os.execl("/usr/bin/rpm-ostree", "rpm-ostree", *args)

    def host_status(self):
        self._rpmostree("status")

    def host_upgrade(self):
        argv = ["upgrade"]
        if self.args.reboot:
            argv.append("--reboot")
        self._rpmostree(*argv)

    def host_rollback(self):
        argv = ["rollback"]
        if self.args.reboot:
            argv.append("--reboot")
        self._rpmostree(*argv)

    def uninstall(self):
        self.inspect = self._inspect_container()
        if self.inspect and self.force:
            self.force_delete_containers()
        if self.name != self.image:
            try:
                # Attempt to remove container, if it exists just return
                self.d.stop(self.name)
                self.d.remove_container(self.name)
                return
            except:
                # On exception attempt to remove image
                pass

        try:
            self.d.stop(self.image)
            self.d.remove_container(self.image)
        except docker.errors.APIError:
            pass
        self.inspect = self._inspect_image()
        if not self.inspect:
            raise ValueError("Image '%s' is not installed" % self.image)

        args = self._get_args("UNINSTALL")
        if args:
            cmd = self.gen_cmd(args + map(pipes.quote, self.args.args))
            self.writeOut(cmd)
            subprocess.check_call(cmd, env=self.cmd_env, shell=True)
        subprocess.check_call(["/usr/bin/docker", "rmi", self.image])

    @property
    def cmd_env(self):
        return {'NAME': self.name, 'IMAGE': self.image,
                "CONFDIR": "/etc/%s" % self.name,
                "LOGDIR": "/var/log/%s" % self.name,
                "DATADIR":"/var/lib/%s" % self.name}

    def gen_cmd(self,cargs):
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
        self.inspect = self._inspect_image()
        if not self.inspect:
            self.update()
            self.inspect = self._inspect_image()

        labels = self._get_labels()
        buf = ""
        for label in labels:
            buf +=("%-13s: %s\n" % (label, labels[label]))
        if buf:
            self.writeOut(buf.strip())
        else:
            raise ValueError("No label information for that "
                    "image.")

    def install(self):
        self.inspect = self._inspect_image()
        if not self.inspect:
            self.update()
            self.inspect = self._inspect_image()

        args = self._get_args("INSTALL")
        if args:
            cmd = self.gen_cmd(args + map(pipes.quote, self.args.args))
            self.writeOut(cmd)

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
        version = ("%s-%s-%s" % (get_label("Name"),get_label("Version"), get_label("Release"))).strip("-")
        return({ "Id": image['Id'], "Name": get_label("Name"), "Version" : version,  "Tag": findRepoTag(self.d, image['Id']), "Parent": image['Parent']})

    def get_layers(self):
        layers = []
        layer = self._get_layer(self.image)
        layers.append(layer)
        while layer["Parent"] != "":
            layer = self._get_layer(layer["Parent"])
            layers.append(layer)
        return layers

    def _get_image(self, image):
        def get_label(label):
            return self.get_label(label, image["Id"])

        return { "Id": image['Id'], "Name": get_label("Name"), "Version" : ("%s-%s-%s" % (get_label("Name"),get_label("Version"),get_label("Release"))).strip(":"), "Tag": image["RepoTags"][0]}

    def get_images(self):
        if len(self.images) > 0:
            return self.images

        images = self.d.images()
        for image in images:
            self.images.append(self._get_image(image))

        return self.images

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
            version = "%s-%s-%s" % (current_name,get_label("Version"),get_label("Release"))

        prev = ""
        name = None
        buf = ""
        for layer in self.get_layers():
            if name == layer["Name"]:
                continue
            name = layer["Name"]
            if len(name)>0:
                for i in self.get_images():
                    if i["Name"] == name:
                        if i["Version"] > layer["Version"]:
                            buf = ("Image '%s' contains a layer '%s' that is out of date.\nImage version '%s' is available, current version could container vulnerabilities." % (self.image, layer["Version"], i["Version"]))
                            buf += ("You should rebuild the '%s' image using docker build." % (self.image))
                            break
        return buf

    def print_verify(self):
        self.writeOut(self.verify())

    def mount(self):
        if os.geteuid() != 0:
            raise ValueError("This command must be run as root.")
        try:
            options = [opt for opt in self.args.options.split(',') if opt]
            mount.DockerMount(self.args.mountpoint,
                              self.args.live).mount(self.args.image, options)

            if not self.args.no_bind:
                mount.Mount.mount_path(os.path.join(self.args.mountpoint,
                                                    "rootfs"),
                                       self.args.mountpoint, bind=True)

        except mount.MountError as dme:
            raise ValueError(str(dme))

    def unmount(self):
        if os.geteuid() != 0:
            raise ValueError("This command must be run as root.")
        try:
            dev = mount.Mount.get_dev_at_mountpoint(self.args.mountpoint)

            # If there's a bind-mount over the directory, unbind it.
            if dev.rsplit('[', 1)[-1].strip(']') == '/rootfs':
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
            return [ self._get_layer(self.image) ]

    def print_version(self):
        for layer in self.version():
            version = layer["Version"]
            if layer["Version"] == '':
                version="None"
            self.writeOut("%s %s %s" % (layer["Id"],version,layer["Tag"]))

def SetFunc(function):
    class customAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            setattr(namespace, self.dest, function)
    return customAction
