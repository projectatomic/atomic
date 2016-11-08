import os
from Atomic.backends.backend import Backend
from Atomic.objects.image import Image
from Atomic.objects.container import Container
from Atomic.syscontainers import SystemContainers
from Atomic.objects.layer import Layer

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

    def _make_container(self, info):
        container_id = info['Id']

        runtime = self.syscontainers.get_container_runtime_info(container_id)

        container = Container(container_id, backend=self)
        container.name = container_id
        container.id = container_id
        container.created = info['Created']
        container.status = runtime['status']
        container.input_name = container_id
        container.original_structure = info
        container.deep = True
        container.image = info['Image']

        return container

    def _make_image(self, image, info):
        name = info['Id']
        image = Image(image, backend=self, remote=False)
        image.name = name
        image.config = info
        image.backend = self
        image.id = name
        image.registry = None
        image.repo = None
        image.image = name
        image.tag = name
        image.repotags = info['RepoTags']
        image.created = info['Created']
        image.size = None
        image.original_structure = info
        image.input_name = info['Id']
        image.deep = True
        image.labels = info['Labels']
        image.version = image.get_label("Version")
        image.release = image.get_label("Release")
        image.digest = None
        image.os = image.get_label("Os")
        image.arch = image.get_label("Arch")
        image.graph_driver = None
        return image

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

    def stop_container(self, name):
        return self.syscontainers.stop_service(name)

    def get_images(self, get_all=False):
        return [self._make_image(x['Id'], x) for x in self.syscontainers.get_system_images(get_all=get_all)]

    def get_containers(self):
        return [self._make_container(x) for x in self.syscontainers.get_containers()]

    def pull_image(self, image, pull_args):
        return self.syscontainers.pull_image(image)

    def delete_image(self, image, force=False):
        return self.syscontainers.delete_image(image)

    def version(self, image):
        return self.get_layers(image)

    def update(self, name, force=False):
        if force or not self.syscontainers.has_image(name):
            return self.syscontainers.update(name)
        return True

    def install(self, image, name):
        return self.syscontainers.install(image, name)

    def uninstall(self, name):
        return self.syscontainers.uninstall(name)

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
