from docker import errors

import Atomic.util as util
from Atomic.backends.backend import Backend
from Atomic.client import AtomicDocker, no_shaw
from Atomic.objects.image import Image
from Atomic.objects.container import Container
from requests import exceptions
from Atomic.trust import Trust
from Atomic.objects.layer import Layer
from dateutil.parser import parse as dateparse
from Atomic import Atomic
import os
from requests.exceptions import HTTPError
from Atomic.backends._docker_errors import NoDockerDaemon

try:
    from subprocess import DEVNULL  # pylint: disable=no-name-in-module
except ImportError:
    DEVNULL = open(os.devnull, 'wb')

class DockerBackend(Backend):
    def __init__(self):
        self.input = None
        self._d = None

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
            con_obj.image_id = con_struct['ImageID']
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
                raise ValueError("Latest version of {} already present.".format(image))
        registry, _, _, tag, _ = util.Decompose(fq_name).all
        image = "docker-daemon:{}".format(image)
        if not image.endswith(tag):
            image += ":{}".format(tag)
        if '@sha256:' in image:
            image = image.replace("@sha256:", ":")

        insecure = True if util.is_insecure_registry(self.d.info()['RegistryConfig'], util.strip_port(registry)) else False
        trust = Trust()
        trust.discover_sigstore(fq_name)
        util.write_out("Pulling {} ...".format(fq_name))
        util.skopeo_copy("docker://{}".format(fq_name), image, debug=debug, insecure=insecure,
                         policy_filename=trust.policy_filename)
        return 0

    def delete_container(self, cid, force=False):
        return self.d.remove_container(cid, force=force)

    def delete_containers_by_image(self, img_obj, force=False):
        containers_by_image = self.get_containers_by_image(img_obj)
        for container in containers_by_image:
            self.delete_container(container.id, force=force)

    def get_containers_by_image(self, img_obj):
        containers = []
        for container in self.get_containers():
            if img_obj.id == container.image_id:
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
        except errors.NotFound:
            pass
        except HTTPError:
            pass

    def update(self, name, force=False, **kwargs):
        debug = kwargs.get('debug', False)
        # A TypeError is thrown if the force keywords is passed in addition to kwargs
        force = kwargs.get('force', False)
        remote_image_obj = self.make_remote_image(name)
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

    def get_dangling_images(self):
        return self._get_images(get_all=True, quiet=True, filters={"dangling": True})

    def install(self, image, name, **kwargs):
        pass

    def uninstall(self, iobject, name=None, **kwargs):
        atomic = kwargs.get('atomic')
        assert(isinstance(atomic, Atomic))
        args = atomic.args
        con_obj = None if not name else self.has_container(name)

        # We have a container by that name, need to stop and delete it
        if con_obj:
            if con_obj.running:
                self.stop_container(con_obj)
            self.delete_container(con_obj.id)

        if args.force:
            self.delete_containers_by_image(iobject, force=True)

        uninstall_command = iobject.get_label('UNINSTALL')
        command_line_args = args.args

        cmd = []
        if uninstall_command:
            try:
                cmd =+ uninstall_command
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
            return util.check_call(cmd, env=atomic.cmd_env())
        return self.delete_image(iobject.image, force=args.force)

    def validate_layer(self, layer):
        pass

    def version(self, image):
        return self.get_layers(image)

    def get_layer(self, image):
        _layer = Layer(self.inspect_image(image))
        _layer.remote = image.remote
        return _layer

    def get_layers(self, image):
        layers = []
        layer = self.get_layer(image)
        layers.append(layer)
        while layer.parent:
            layer = self.get_layer(layer.parent)
            layers.append(layer)
        return layers

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
            if latest_image.id != iobject.image_id:
                util.write_out("The '{}' container is using an older version of the installed\n'{}' container image. If "
                               "you wish to use the newer image,\nyou must either create a new container with a "
                               "new name or\nuninstall the '{}' container. \n\n# atomic uninstall --name "
                               "{} {}\n\nand create new container on the {} image.\n\n# atomic update --force "
                               "{}s\n\n removes all containers based on an "
                               "image.".format(iobject.name, iobject.image_name, iobject.name, iobject.name,
                                               iobject.image_name, iobject.image_name, iobject.image_name))
            if iobject.running:
                return self._running(iobject, args, atomic)
            else:
                return self._start(iobject, args, atomic)

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
        if con_obj.interactive:
            if args.command:
                util.check_call(
                    [atomic.docker_binary(), "start", con_obj.name],
                    stderr=DEVNULL)
                container_command = args.command if isinstance(args.command, list) else args.command.split()
                return util.check_call(
                    [atomic.docker_binary(), "exec", "-t", "-i", con_obj.name] +
                    container_command)
            else:
                return util.check_call(
                    [atomic.docker_binary(), "start", "-i", "-a", con_obj.name],
                    stderr=DEVNULL)
        else:
            if args.command:
                util.check_call(
                    [atomic.docker_binary(), "start", con_obj.name],
                    stderr=DEVNULL)
                return util.check_call(
                    [atomic.docker_binary(), "exec", "-t", "-i", con_obj.name] +
                    con_obj.command)
            else:
                return util.check_call(
                    [atomic.docker_binary(), "start", con_obj.name],
                    stderr=DEVNULL)
