import os
import shutil
import tempfile

from docker import errors

import Atomic.util as util
from Atomic.backends.backend import Backend
from Atomic.client import AtomicDocker, no_shaw
from Atomic.objects.image import Image
from Atomic.objects.container import Container
from requests import exceptions
from Atomic.rpm_host_install import RPMHostInstall
from Atomic.trust import Trust
from Atomic.objects.layer import Layer
from dateutil.parser import parse as dateparse
from Atomic import Atomic
from requests.exceptions import HTTPError
from Atomic.backends._docker_errors import NoDockerDaemon
from Atomic.discovery import RegistryInspectError
from Atomic.atomic import AtomicError
from subprocess import CalledProcessError

try:
    from subprocess import DEVNULL  # pylint: disable=no-name-in-module
except ImportError:
    DEVNULL = open(os.devnull, 'wb')


class ContainerInstallation(object):
    """
    Provides variables which hold data for how build and
    installation process of a container went
    """
    def __init__(self, original_rpm_name, destination_path, installed_files):
        """
        :param original_rpm_name: verbose RPM name
        :param destination_path: path to built RPM
        :param installed_files: list of files provided by the built RPM
        """
        self.original_rpm_name = original_rpm_name
        self.destination_path = destination_path
        self.installed_files = installed_files


def build_rpm_for_docker_backend(image, name, temp_dir, labels):
    """
    build rpm package for specified docker image

    :param image, instance of Atomic.objects.image.Image
    :param name, str, name of the associated container
    :param temp_dir: str, directory where all the data will be processed
    :param labels: dict, these labels come from container image
    :return: instance of StandaloneContainerInstallation
    """
    from Atomic.mount import DockerMount, MountContextManager
    mount_path = os.path.join(temp_dir, "mountpoint")
    destination = os.path.join(temp_dir, "system_rpm")
    os.makedirs(destination)
    os.makedirs(mount_path)
    dm = DockerMount(mount_path)
    cm = MountContextManager(dm, image.id)
    with cm:
        # if we are on devicemapper, the path to container is <mount_point>/hostfs/
        dm_candidate_path = os.path.join(cm.mnt_path, "rootfs")
        if os.path.exists(dm_candidate_path):
            exports_dir = os.path.join(dm_candidate_path, "exports")
        else:
            exports_dir = os.path.join(cm.mnt_path, "exports")
        r = RPMHostInstall.generate_rpm(
            name, image.id, labels, exports_dir, destination)
        return ContainerInstallation(r[0], r[1], r[2])


class DockerBackend(Backend):
    def __init__(self):
        self.input = None
        self._d = None
        self._dangling_images = None

    @property
    def available(self):
        try:
            _ = self.d
            return True
        except NoDockerDaemon:
            return False

    @property
    def d(self):
        if not self._d:
            self._d = AtomicDocker()
            self._ping()
            return self._d
        return self._d

    @property
    def backend(self):
        return "docker"

    def has_image(self, img):
        err_append = "Refine your search to narrow results."
        self.input = img
        image_info = self._get_images(get_all=True)

        img_obj = self.inspect_image(image=img)
        if img_obj:
            return img_obj
        # If we cannot find the image locally AND it has a digest
        # then bail.
        if '@sha256:' in img:
            return None
        name_search = util.image_by_name(img, images=image_info)
        length = len(name_search)
        if length == 0:
            # No dice
            return None
        if length > 1:
            tmp_image = dict((x['Id'], x['RepoTags']) for x in image_info)
            repo_tags = []
            for name in name_search:
                for repo_tag in tmp_image.get(name['Id']):
                    if repo_tag.find(img) > -1:
                        repo_tags.append(repo_tag)
            raise ValueError("Found more than one image possibly "
                             "matching '{0}'. They are:\n    {1} \n{2}"
                             .format(img, "\n    ".join(repo_tags),
                                     err_append))

        inspected = self._inspect_image(img)
        if not inspected:
            return None
        return self._make_image(img, inspected, deep=True)

    def already_has_image(self, local_img, remote_img):
        """
        Returns bool response if the image is already present.  Input must be an image object
        :param img_obj: an image object
        :return:
        """
        if local_img == remote_img:
            return True
        return False

    def has_container(self, container):
        con_obj = self.inspect_container(container)
        if con_obj:
            self.input = container
            return con_obj
        return None

    def _inspect_image(self, image):
        try:
            inspect_data = self.d.inspect_image(image)
        except errors.NotFound:
            # We might be looking for something by digest
            if "@sha256:" in image:
                return  self._inspect_image_by_hash(image)
            return None
        return inspect_data

    def _inspect_image_by_hash(self, image):
        input_digest = util.Decompose(image).digest
        all_images = self.get_images(get_all=True)
        for _image in all_images:
            if not _image.repotags:
                continue
            for repo_digest in _image.repotags:
                if no_shaw(input_digest) in repo_digest:
                    return self.d.inspect_image(_image.id)
        return None

    def inspect_image(self, image):
        inspect_data = self._inspect_image(image)
        if inspect_data:
            img_obj = self._make_image(image, inspect_data, deep=True)
            return img_obj
        return None

    def _make_image(self, image, img_struct, deep=False, remote=False):
        img_obj = Image(image, remote=remote)
        img_obj.backend = self

        if not remote:
            img_obj.id = img_struct['Id']
            img_obj.repotags = img_struct['RepoTags']
            img_obj.created = img_struct['Created']
            img_obj.size = img_struct['Size']
            img_obj.virtual_size = img_struct['VirtualSize']
            img_obj.original_structure = img_struct

        if deep:
            img_obj.deep = True
            img_obj.repotags = img_struct['RepoTags']
            img_obj.config = img_struct['Config'] or {}
            img_obj.labels = img_obj.config.get("Labels", None)
            img_obj.os = img_struct['Os']
            img_obj.arch = img_struct['Architecture']
            img_obj.graph_driver = img_struct['GraphDriver']
            img_obj.version = img_obj.get_label('Version')
            img_obj.release = img_obj.get_label('Release')
            img_obj.parent = img_struct['Parent']
            img_obj.original_structure = img_struct
            img_obj.cmd = img_obj.original_structure['Config']['Cmd']
        return img_obj

    def _make_container(self, container, con_struct, deep=False):
        con_obj = Container(container, backend=self)
        con_obj.id = con_struct['Id']
        try:
            con_obj.created = float(con_struct['Created'])
        except ValueError:
            con_obj.created = dateparse(con_struct['Created']).strftime("%F %H:%M") # pylint: disable=no-member
        con_obj.original_structure = con_struct
        try:
            con_obj.name = con_struct['Names'][0]
        except KeyError:
            con_obj.name = con_struct['Name']
        con_obj.input_name = container
        con_obj.backend = self
        try:
            con_obj.command = con_struct['Command']
        except KeyError:
            con_obj.command = con_struct['Config']['Cmd']

        try:
            con_obj.state = con_struct.get('State', None) or con_struct.get['State'].get('Status', None)
        except TypeError:
            # Docker 1.10 on F24 has a different structure
            con_obj.state = con_struct['Status']

        if isinstance(con_obj.state, dict):
            con_obj.state = con_obj.state['Status']
        con_obj.running = True if con_obj.state.lower() in ['true', 'running'] else False

        if deep:
            # Add in the deep inspection stuff
            con_obj.status = con_struct['State']['Status']
            con_obj.image = con_struct['Image']
            con_obj.image_name = con_struct['Config']['Image']
            con_obj.labels = con_struct['Config']['Labels']

        else:
            con_obj.status = con_struct['Status']
            con_obj.image = con_struct['ImageID']
            con_obj.image_name = con_struct['Image']

        return con_obj

    def _inspect_container(self, container):
        try:
            inspect_data = self.d.inspect_container(container)
        except errors.NotFound:
            return None
        return inspect_data

    def inspect_container(self, container):
        inspect_data = self._inspect_container(container)
        if inspect_data:
            return self._make_container(container, inspect_data, deep=True)
        return None

    def get_images(self, get_all=False):
        images = self._get_images(get_all=get_all)
        image_objects = []
        for image in images:
            image_objects.append(self._make_image(image['Id'], image))
        return image_objects

    def make_remote_image(self, image):
        img_obj = self._make_remote_image(image)
        img_obj.populate_remote_inspect_info()
        return img_obj

    def _make_remote_image(self, image):
        return self._make_image(image, None, remote=True)

    def get_containers(self):
        containers = self._get_containers()
        con_objects = []
        for con in containers:
            con_objects.append(self._make_container(con['Id'], con))
        return con_objects

    def _get_images(self, get_all=False, quiet=False, filters=None):
        if filters:
            assert isinstance(filters, dict)
        else:
            filters = {}
        return self.d.images(all=get_all, quiet=quiet, filters=filters)

    def _get_containers(self):
        return self.d.containers(all=True)

    def start_container(self, name):
        if not self.has_container(name):
            raise ValueError("Unable to locate container '{}' in {} backend".format(name, self.backend))
        return self.d.start(name)

    def stop_container(self, con_obj, **kwargs):
        atomic = kwargs.get('atomic')
        args = kwargs.get('args')
        con_obj.stop_args = con_obj.get_label('stop')
        if con_obj.stop_args:
            try:
                cmd = atomic.gen_cmd(con_obj.stop_args.split() + atomic.quote(args.args))
            except TypeError:
                cmd = atomic.gen_cmd(con_obj.stop_args + atomic.quote(args.args))
            cmd = atomic.sub_env_strings(cmd)
            atomic.display(cmd)
            if args.display:
                return 0
            # There should be some error handling around this
            # in case it fails.  And what should then be done?
            return util.check_call(cmd, env=atomic.cmd_env())
        elif args.display:
            return 0

        return self.d.stop(con_obj.id)


    def pull_image(self, image, remote_image_obj, **kwargs):
        assert(isinstance(remote_image_obj, Image))
        debug = kwargs.get('debug', False)
        if image.startswith("dockertar:"):
            path = image.replace("dockertar:", "", 1)
            with open(path, 'rb') as f:
                self.d.load_image(data=f)
            return 0
        fq_name = remote_image_obj.fq_name
        local_image = self.has_image(image)
        if local_image is not None:
            if self.already_has_image(local_image, remote_image_obj):
                raise util.ImageAlreadyExists(image)
        registry, _, _, tag, _ = util.Decompose(fq_name).all
        image = "docker-daemon:{}".format(fq_name)
        if not image.endswith(tag):
            image += ":{}".format(tag)
        if '@sha256:' in image:
            image = image.replace("@sha256:", ":")

        src_creds = kwargs.get('src_creds')
        insecure = True if util.is_insecure_registry(self.d.info()['RegistryConfig'], registry) else False
        trust = Trust()
        trust.discover_sigstore(fq_name)
        util.write_out("Pulling {} ...".format(fq_name))
        util.skopeo_copy("docker://{}".format(fq_name), image, debug=debug, insecure=insecure,
                         policy_filename=trust.policy_filename, src_creds=src_creds)
        return 0

    def delete_container(self, container, force=False):
        return self.d.remove_container(container, force=force)

    def delete_containers_by_image(self, img_obj, force=False):
        containers_by_image = self.get_containers_by_image(img_obj)
        for container in containers_by_image:
            self.delete_container(container.id, force=force)

    def get_containers_by_image(self, img_obj):
        containers = []
        for container in self.get_containers():
            if img_obj.id == container.image:
                containers.append(container)
        return containers


    def _ping(self):
        '''
        Check if the docker daemon is running; if not, exit with
        message and return code 1
        '''
        try:
            self.d.ping()
        except exceptions.ConnectionError:
            raise NoDockerDaemon()

    def delete_image(self, image, force=False):
        assert(image is not None)
        try:
            return self.d.remove_image(image, force=force)
        except errors.APIError as e:
            raise ValueError(str(e))
        except errors.NotFound: # pylint: disable=bad-except-order
            pass
        except HTTPError:
            pass

    def update(self, name, **kwargs):
        debug = kwargs.get('debug', False)
        # A TypeError is thrown if the force keywords is passed in addition to kwargs
        force = kwargs.get('force', False)
        local_only = False
        try:
            remote_image_obj = self.make_remote_image(name)
        except RegistryInspectError:
            # We might be dealing with a local only image
            local_only = True
        if local_only:
            img_obj = kwargs.get('image_object')
            return self.delete_image(img_obj.id, force=True)
        else:
            # pull_image will raise a ValueError if the "latest" image is already present
            self.pull_image(name, remote_image_obj, debug=debug)
        # Only delete containers if a new image is actually pulled.
        img_obj = self.inspect_image(name)
        if force:
            self.delete_containers_by_image(img_obj)

    def prune(self):
        for iid in self.get_dangling_images():
            self.delete_image(iid, force=True)
            util.write_out("Removed dangling Image {}".format(iid))
        return 0

    def get_dangling_images(self, force_update=True):
        if self._dangling_images == None or force_update:
            self._dangling_images = self._get_images(get_all=True, quiet=True, filters={"dangling": True})
        return self._dangling_images

    def install(self, image, name, **kwargs):
        pass

    def rpm_install(self, image, name):
        """
        Install system rpm for selected docker image on this system.

        :param image: instance of Atomic.objects.image.Image
        :param name, str, name of the associated container
        :return: instance of ContainerInstallation or None if no rpm was installed
        """
        labels = image.labels or {}
        # we actually don't care about value of the label
        if 'atomic.has_install_files' in labels:
            # we are going to install the system package - the image provides some files to host
            temp_dir = tempfile.mkdtemp()
            try:
                installation = build_rpm_for_docker_backend(image, name, temp_dir, labels)
                RPMHostInstall.install_rpm(installation.destination_path)
            finally:
                shutil.rmtree(temp_dir)
            return installation
        # if the label is not present, we won't install any package on the system

    def uninstall(self, iobject, name=None, **kwargs):
        atomic = kwargs.get('atomic')
        ignore = kwargs.get('ignore')
        assert(isinstance(atomic, Atomic))
        args = atomic.args
        con_obj = None if not name else self.has_container(name)
        # We have a container by that name, need to stop and delete it
        if con_obj:
            if con_obj.running:
                self.stop_container(con_obj, args=atomic.args, atomic=atomic)
            # Check if the container is still present.  stop_container might
            # have deleted it
            if self.has_container(name):
                self.delete_container(con_obj.id)

        if args.force:
            self.delete_containers_by_image(iobject, force=True)
        else:
            containers_by_image = self.get_containers_by_image(iobject)
            if len(containers_by_image) > 0:
                containers_active = ", ".join([i.name for i in containers_by_image])
                raise ValueError("Containers `%s` are using this image, delete them first or use --force" % containers_active)

        uninstall_command = iobject.get_label('UNINSTALL')
        command_line_args = args.args

        cmd = []
        if uninstall_command:
            try:
                cmd = cmd + uninstall_command
            except TypeError:
                cmd = cmd + uninstall_command.split()
        if command_line_args:
            cmd += command_line_args

        cmd = atomic.gen_cmd(cmd)
        cmd = atomic.sub_env_strings(cmd)
        atomic.display(cmd)
        if args.display:
            return 0


        if cmd:
            result = util.check_call(cmd, env=atomic.cmd_env())
            if result == 0:
                util.InstallData.delete_by_id(iobject.id, name, ignore=ignore)
            return result

        system_package_nvra = None
        if not ignore:
            install_data = util.InstallData.get_install_data_by_id(iobject.id)
            system_package_nvra = install_data.get("system_package_nvra", None)
        if system_package_nvra:
            RPMHostInstall.uninstall_rpm(system_package_nvra)

        # Delete the entry in the install data
        last_image = util.InstallData.delete_by_id(iobject.id, name, ignore=ignore)
        if last_image:
            return self.delete_image(iobject.image, force=args.force)

    def version(self, image):
        return self.get_layers(image)

    def get_layer(self, image):
        _layer = Layer(self.inspect_image(image))
        # Disabling this assignment; not sure where it used and why
        # Enabled it will cause an Attribute Error because image is
        # a str object and has not attrs.  Leaving for historical
        # purposes in case I break something.

        #_layer.remote = image.remote
        return _layer

    def get_layers(self, image):
        layers = []
        layer = self.get_layer(image)
        layers.append(layer)
        while layer.parent:
            layer = self.get_layer(layer.parent)
            layers.append(layer)
        return layers

    def replace_existing_container(self, _iobject, _requested_image, _args):
        if _args.debug:
            util.write_out("Removing the container {} and running with {}".format(_iobject.name,
                                                                                  _requested_image.fq_name))
        self.delete_container(_iobject.id, force=True)
        _iobject = _requested_image
        if _args.command:
            _iobject.user_command = _args.command
        return _iobject

    def run(self, iobject, **kwargs):
        def add_string_or_list_to_list(list_item, value):
            if not isinstance(value, list):
                value = value.split()
            list_item += value
            return list_item

        atomic = kwargs.get('atomic', None)
        args = kwargs.get('args')
        # atomic must be an instance of Atomic
        # args must be a argparse Namespace
        assert(isinstance(atomic, Atomic))
        # The object is a container
        # If container exists and not started, start it
        # If container exists and is started, execute command inside it (docker exec)
        # If container doesn't exist, create one and start it
        if args.command:
            iobject.user_command = args.command
        if isinstance(iobject, Container):
            latest_image = self.inspect_image(iobject.image_name)
            if latest_image.id != iobject.image:
                util.write_out("The '{}' container is using an older version of the installed\n'{}' container image. If "
                               "you wish to use the newer image,\nyou must either create a new container with a "
                               "new name or\nuninstall the '{}' container. \n\n# atomic uninstall --name "
                               "{} {}\n\nand create new container on the {} image.\n\n# atomic update --force "
                               "{}s\n\n removes all containers based on an "
                               "image.".format(iobject.name, iobject.image_name, iobject.name, iobject.name,
                                               iobject.image_name, iobject.image_name, iobject.image_name))

            requested_image = self.has_image(args.image)
            if requested_image is None:
                requested_image = self.has_image(iobject.image)

            if iobject.running:
                if args.replace:
                    iobject = self.replace_existing_container(iobject, requested_image, args)
                    return self.run(iobject, args=args, atomic=atomic)
                return self._running(iobject, args, atomic)
            else:
                # Container with the name exists
                image_id = iobject.image
                if requested_image.id != image_id:
                    if args.replace:
                        iobject = self.replace_existing_container(iobject, requested_image, args)
                    else:
                        try:
                            requested_image_fq_name = requested_image.fq_name
                        except RegistryInspectError:
                            requested_image_fq_name = args.image
                        raise AtomicError("Warning: container '{}' already points to {}\nRun 'atomic run {}' to run "
                                          "the existing container.\nRun 'atomic run --replace '{}' to replace "
                                          "it".format(iobject.name,
                                                      iobject.original_structure['Config']['Image'],
                                                      iobject.name,
                                                      requested_image_fq_name))
                else:
                    if args.replace:
                        iobject = self.replace_existing_container(iobject, requested_image, args)
                    else:
                        return self._start(iobject, args, atomic)

        if iobject.get_label('INSTALL') and not args.ignore and not util.InstallData.image_installed(iobject):
            raise ValueError("The image '{}' appears to have not been installed and has an INSTALL label.  You "
                             "should install this image first.  Re-run with --ignore to bypass this "
                             "error.".format(iobject.name or iobject.image))
        # The object is an image
        command = []
        if iobject.run_command:
            command = add_string_or_list_to_list(command, iobject.run_command)
            if iobject.user_command:
                command = add_string_or_list_to_list(command, iobject.user_command)
            opts_file = iobject.get_label("RUN_OPTS_FILE")
            if opts_file:
                opts_file = atomic.sub_env_strings("".join(opts_file))
                if opts_file.startswith("/"):
                    if os.path.isfile(opts_file):
                        try:
                            atomic.run_opts = open(opts_file, "r").read()
                        except IOError:
                            raise ValueError("Failed to read RUN_OPTS_FILE %s" % opts_file)
                else:
                    raise ValueError("Will not read RUN_OPTS_FILE %s: not absolute path" % opts_file)
        else:
            command += [atomic.docker_binary(), "run"]
            if os.isatty(0):
                command += ["-t"]
            if args.detach:
                command += ["-d"]
            command += atomic.SPC_ARGS if args.spc else atomic.RUN_ARGS
            if iobject.user_command:
                command = add_string_or_list_to_list(command, iobject.user_command)

        if len(command) > 0 and command[0] == "docker":
            command[0] = atomic.docker_binary()

        if iobject.cmd and not iobject.user_command and not iobject.run_command:
            cmd = iobject.cmd if isinstance(iobject.cmd, list) else iobject.cmd.split()
            command += cmd
        command = atomic.gen_cmd(command)
        command = atomic.sub_env_strings(command)
        atomic.display(command)
        if atomic.args.display:
            return

        if not atomic.args.quiet:
            self.check_args(command)
        return util.check_call(command, env=atomic.cmd_env())

    @staticmethod
    def check_args(cmd):
        found_sec_arg = False
        security_args = {
            '--privileged':
                'This container runs without separation and should be '
                'considered the same as root on your system.',
            '--cap-add':
                'Adding capabilities to your container could allow processes '
                'from the container to break out onto your host system.',
            '--security-opt label:disable':
                'Disabling label separation turns off tools like SELinux and '
                'could allow processes from the container to break out onto '
                'your host system.',
            '--security-opt label=disable':
                'Disabling label separation turns off tools like SELinux and '
                'could allow processes from the container to break out onto '
                'your host system.',
            '--net=host':
                'Processes in this container can listen to ports (and '
                'possibly rawip traffic) on the host\'s network.',
            '--pid=host':
                'Processes in this container can see and interact with all '
                'processes on the host and disables SELinux within the '
                'container.',
            '--ipc=host':
                'Processes in this container can see and possibly interact '
                'with all semaphores and shared memory segments on the host '
                'as well as disables SELinux within the container.'
        }

        for sec_arg in security_args:
            if sec_arg in cmd:
                if not found_sec_arg:
                    util.write_out("\nThis container uses privileged "
                                   "security switches:")
                util.write_out("\n\033[1mINFO: {}\033[0m "
                               "\n{}{}".format(sec_arg, " " * 6,
                                               security_args[sec_arg]))
                found_sec_arg = True
        if found_sec_arg:
            util.write_out("\nFor more information on these switches and their "
                           "security implications, consult the manpage for "
                           "'docker run'.\n")

    def _running(self, con_obj, args, atomic):
        requested_image = self.has_image(args.image)
        if requested_image is not None and con_obj.image != requested_image.id:
            requested_image_fq_name = requested_image.fq_name
            raise AtomicError("Warning: container '{}' already points to {}\nRun 'atomic run {}' to run "
                                          "the existing container.\nRun 'atomic run --replace '{}' to replace "
                                          "it".format(con_obj.name,
                                                      con_obj.original_structure['Config']['Image'],
                                                      con_obj.name,
                                                      requested_image_fq_name))
        if con_obj.interactive:
            container_command = con_obj.command if not args.command else args.command
            container_command = container_command if not isinstance(container_command, list) else " ".join(container_command)
            cmd = [atomic.docker_binary(), "exec", "-t", "-i", con_obj.name] + container_command.split()
            if args.display:
                return atomic.display(" ".join(cmd))
            else:
                return util.check_call(cmd, stderr=DEVNULL)
        else:
            command = con_obj.command if not args.command else args.command
            try:
                cmd = [atomic.docker_binary(), "exec", "-t", "-i", con_obj.name] + command
            except TypeError:
                cmd = [atomic.docker_binary(), "exec", "-t", "-i", con_obj.name] + command.split()

            if args.command:
                if args.display:
                    return util.write_out(" ".join(cmd))
                else:
                    return util.check_call(cmd, stderr=DEVNULL)
            else:
                if not args.display:
                    util.write_out("Container is running")

    def _start(self, con_obj, args, atomic):
        exec_error = "Failed to execute the command inside the existing container. In some situations " \
                     "this can happen because the entry point command of the container only runs for " \
                     "a short time. You might want to replace the container by executing your " \
                     "command with --replace. Note any updates to the existing container will be lost"

        if con_obj.interactive:
            if args.command:
                util.check_call([atomic.docker_binary(), "start", con_obj.name], stderr=DEVNULL)
                container_command = args.command if isinstance(args.command, list) else args.command.split()
                try:
                    return util.check_call([atomic.docker_binary(), "exec", "-t", "-i", con_obj.name] + container_command)
                except CalledProcessError as e:
                    if args.debug:
                        util.write_out(str(e))
                    raise AtomicError(exec_error)


            else:
                return util.check_call(
                    [atomic.docker_binary(), "start", "-i", "-a", con_obj.name],
                    stderr=DEVNULL)
        else:
            if args.command:
                util.check_call(
                    [atomic.docker_binary(), "start", con_obj.name],
                    stderr=DEVNULL)
                try:
                    return util.check_call(
                        [atomic.docker_binary(), "exec", "-t", "-i", con_obj.name] +
                        con_obj.command)
                except CalledProcessError as e:
                    if args.debug:
                        util.write_out(str(e))
                    raise AtomicError(exec_error)

            else:
                return util.check_call(
                    [atomic.docker_binary(), "start", con_obj.name],
                    stderr=DEVNULL)

    def tag_image(self, _src, _dest):
        registry, repo, image, tag, _ = util.Decompose(_dest).all
        result = registry
        if repo:
            result += "/{}".format(repo)
        result += "/{}".format(image)
        if result.startswith("/"):
            result = result[1:]
        return self.d.tag(_src, result, tag=tag)

    def validate_layer(self, layer):
        """
        Validates a docker image by mounting the image on a rootfs and validate that
        rootfs against the manifests that were created. Note that it won't be validated
        layer by layer.
        :param:
        :return: None
        """
        inspect = self._inspect_image(image=layer)
        if inspect is None:
            return None

        iid = inspect['RepoTags'][0]
        manifestname = os.path.join(util.ATOMIC_VAR_LIB, "gomtree-manifests/%s.mtree" % iid)
        if not os.path.exists(manifestname):
            return
        tmpdir = tempfile.mkdtemp()
        try:
            from Atomic.mount import Mount
            m = Mount()
            m.args = []
            m.image = iid
            m.storage = "docker"
            m.mountpoint = tmpdir
            m.mount()
            try:
                r = util.validate_manifest(manifestname, img_rootfs=tmpdir, keywords="type,uid,gid,mode,size,sha256digest")
                if r.return_code != 0:
                    util.write_err(r.stdout)
            finally:
                m.unmount()
        finally:
            shutil.rmtree(tmpdir)

    @staticmethod
    def get_gomtree_manifest(layer, root=os.path.join(util.ATOMIC_VAR_LIB, "gomtree-manifests")):
        manifestpath = os.path.join(root, "%s.mtree" % layer)
        if os.path.isfile(manifestpath):
            return manifestpath
        return None

