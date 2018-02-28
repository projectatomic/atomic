import os
from Atomic.backends.backend import Backend
from Atomic.objects.image import Image
from Atomic.objects.container import Container
from Atomic.syscontainers import SystemContainers
from Atomic.objects.layer import Layer
from json import loads as json_loads
from Atomic.util import Decompose

class OSTreeBackend(Backend):

    def __init__(self):
        self.input = None
        self.syscontainers = SystemContainers()
        class Args:
            def __init__(self):
                self.system = os.getuid() == 0
                self.user = not self.system
                self.setvalues = {}
                self.remote = False

        self.syscontainers.set_args(Args())

    @property
    def backend(self):
        return "ostree"

    def available(self):
        return self.syscontainers.available

    def _make_container(self, info):
        container_id = info['Id']
        runtime = self.syscontainers.get_container_runtime_info(container_id)
        container = Container(container_id, backend=self)
        container.name = container_id
        container.command = info['Command']
        container.id = container_id
        container.runtime = info['Runtime']
        container.image_name = info['Image']
        container.image = info['ImageID']
        container.created = info['Created']
        container.status = container.state = runtime['status']
        container.input_name = container_id
        container.original_structure = info
        container.deep = True
        container.running = False if container.status == 'inactive' else True
        return container

    def _make_image(self, image, info, remote=False):
        img_obj = Image(image, backend=self, remote=remote)
        if remote:
            return img_obj
        name = info['Id']
        img_obj.input_name = image
        img_obj.name = image
        img_obj.config = info
        img_obj.backend = self
        img_obj.id = name
        img_obj.registry, img_obj.repo, img_obj.image, img_obj.tag, _ = Decompose(image).all
        img_obj.repotags = info['RepoTags']
        img_obj.created = info['Created']
        img_obj.size = info.get('VirtualSize', None)
        img_obj.virtual_size = info.get('VirtualSize', None)
        img_obj.original_structure = info
        img_obj.deep = True
        img_obj.labels = info.get('Labels', None)
        img_obj.version = img_obj.get_label("Version")
        img_obj.release = img_obj.get_label("Release")
        ostree_manifest = self.syscontainers.get_manifest(image)
        if ostree_manifest:
            ostree_manifest = json_loads(ostree_manifest)
        img_obj.digest = None if ostree_manifest is None else ostree_manifest.get('Digest') or ostree_manifest.get('digest')
        img_obj.os = img_obj.get_label("Os")
        img_obj.arch = img_obj.get_label("Arch")
        img_obj.graph_driver = None
        return img_obj

    def has_image(self, img):
        if self.syscontainers.has_image(img):
            return self.inspect_image(img)
        return None

    def has_container(self, container):
        if self.syscontainers.get_checkout(container):
            return self.inspect_container(container)
        return None

    def inspect_image(self, image):
        try:
            return self._make_image(image, self.syscontainers.inspect_system_image(image))
        except ValueError:
            return None

    def inspect_container(self, container):
        containers = self.syscontainers.get_containers(containers=[container])
        if len(containers) == 0:
            return None
        return self._make_container(containers[0])

    def start_container(self, name):
        return self.syscontainers.start_service(name)

    def stop_container(self, con_obj, **kwargs):
        return self.syscontainers.stop_service(con_obj.id)

    def get_images(self, get_all=False):
        return [self._make_image(x['Id'], x) for x in self.syscontainers.get_system_images(get_all=get_all)]

    def get_containers(self):
        return [self._make_container(x) for x in self.syscontainers.get_containers()]

    def pull_image(self, image, remote_image_obj=None, **kwargs):
        return self.syscontainers.pull_image(image, **kwargs)

    def delete_image(self, image, force=False):
        return self.syscontainers.delete_image(image)

    def version(self, image):
        return self.get_layers(image)

    def update(self, name, **kwargs):
        force = kwargs.get('force', False)
        if force:
            raise ValueError("--force is not supported by ostree images")
        return self.syscontainers.pull_image(name)

    def install(self, image, name, **kwargs):
        return self.syscontainers.install(image, name)

    def uninstall(self, iobject, name=None, **kwargs):
        if name is not None:
            raise ValueError("System containers do not support --name. Please use atomic uninstall NAME")
        return self.syscontainers.uninstall(iobject.name)

    def prune(self):
        return self.syscontainers.prune_ostree_images()

    def validate_layer(self, layer):
        return self.syscontainers.validate_layer(layer)

    def _get_layer(self, image):
        return Layer(self.inspect_image(image))

    def get_layers(self, image):
        layers = []
        layer = self._get_layer(image)
        layers.append(layer)
        while layer.parent:
            layer = self._get_layer(layer.parent)
            layers.append(layer)
        return layers

    @staticmethod
    def get_dangling_images(force_update=True):  # pylint: disable=unused-argument
        return []

    def make_remote_image(self, image):
        img_obj = self._make_remote_image(image)
        img_obj.populate_remote_inspect_info()
        return img_obj

    def _make_remote_image(self, image):
        return self._make_image(image, None, remote=True)

    def delete_container(self, container, force=False):
        return self.syscontainers.uninstall(container)

    def run(self, iobject, **kwargs):
        args = kwargs.get('args')
        name = args.image
        if args.name is not None:
            raise ValueError("--name is not supported by this backend")
        if len(args.command) == 0:
            return self.syscontainers.start_service(name)
        self.syscontainers.set_args(args)
        return self.syscontainers.container_exec(name, args.detach, args.command)

    def tag_image(self, src, dest):
        return self.syscontainers.tag_image(src, dest)
