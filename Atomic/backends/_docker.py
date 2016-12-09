from docker import errors

import Atomic.util as util
from Atomic.backends.backend import Backend
from Atomic.client import AtomicDocker
from Atomic.objects.image import Image
from Atomic.objects.container import Container
from requests import exceptions
from Atomic.trust import Trust
from Atomic.objects.layer import Layer
from dateutil.parser import parse as dateparse

class DockerBackend(Backend):
    def __init__(self):
        self.input = None
        self._d = None

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
        return self._make_image(img, self._inspect_image(img), deep=True)

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
            return None
        return inspect_data

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

        con_obj.state = con_struct.get('State', None) or con_struct.get['State'].get('Status', None)
        if isinstance(con_obj.state, dict):
            con_obj.state = con_obj.state['Status']
        con_obj.running = True if con_obj.state.lower() in ['true', 'running'] else False

        if deep:
            # Add in the deep inspection stuff
            con_obj.status = con_struct['State']['Status']
            con_obj.image = con_struct['Image']
            con_obj.image_name = con_struct['Config']['Image']

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

    def stop_container(self, name):
        stop_obj = self.inspect_container(name)
        if not stop_obj:
            raise ValueError("Unable to find container '{}'".format(name))
        if not stop_obj.running:
            raise ValueError("Container '{}' is not running".format(name))
        return self.d.stop(name)

    def pull_image(self, image, pull_args):
        # Add this when atomic registry is incorporated.
        # if self.args.reg_type == "atomic":
        #     pull_uri = 'atomic:'
        # else:
        #     pull_uri = 'docker://'
        img_obj = self._make_remote_image(image)
        fq_name = img_obj.fq_name
        insecure = True if util.is_insecure_registry(self.d.info()['RegistryConfig'], util.strip_port(img_obj.registry)) else False

        # This needs to be re-enabled with Aaron's help
        trust = Trust()
        trust.set_args(pull_args)
        trust.discover_sigstore(fq_name)

        util.write_out("Pulling {} ...".format(fq_name))
        util.skopeo_copy("docker://{}".format(fq_name),
                         "docker-daemon:{}".format(image),
                         debug=pull_args.debug, insecure=insecure,
                         policy_filename=pull_args.policy_filename)

    def delete_container(self, cid, force=False):
        self.d.remove_container(cid, force=force)

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

    @staticmethod
    def _interactive(con_obj):
        config = con_obj.original_structure['Config']
        if all([config.get('AttachStdin', False), config.get('AttachStdout', False), config.get('AttachStderr', False)]):
            return True
        return False

    def _ping(self):
        '''
        Check if the docker daemon is running; if not, exit with
        message and return code 1
        '''
        try:
            self.d.ping()
        except exceptions.ConnectionError:
            raise util.NoDockerDaemon()

    def delete_image(self, image, force=False):
        return self.d.remove_image(image, force=force)

    def update(self, name, force=False):
        img_obj = self.inspect_image(name)
        if force:
            self.delete_containers_by_image(img_obj)
        registry = util.Decompose(img_obj.fq_name).registry
        return util.skopeo_copy("docker://{}".format(name),
                                "docker-daemon:{}".format(img_obj.fq_name),
                                util.is_insecure_registry(self.d.info()['RegistryConfig'], util.strip_port(registry)))

    def prune(self):
        for iid in self.get_dangling_images():
            self.delete_image(iid, force=True)
            util.write_out("Removed dangling Image {}".format(iid))
        return 0

    def get_dangling_images(self):
        return self._get_images(get_all=True, quiet=True, filters={"dangling": True})

    def install(self, image, name):
        pass

    def uninstall(self, name):
        pass

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


