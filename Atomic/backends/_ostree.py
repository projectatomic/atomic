import os
from Atomic.backends.backend import Backend
from Atomic.objects.image import Image
from Atomic.objects.container import Container
from Atomic.syscontainers import SystemContainers

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

    def _make_image(self, info):
        name = info['Id']

        image = Image(name, self)

        image.name = name
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

        image.fq_name = name
        image.version = info['Version']
        image.release = info['Labels']['Release'] if 'Release' in info['Labels'] else None
        image.digest = None
        image.labels = info['Labels']
        image.os = info['Labels']['OS'] if 'OS' in info['Labels'] else None
        image.arch = info['Labels']['Arch'] if 'Arch' in info['Labels'] else None
        image.graph_driver = None

        return image

    def has_image(self, img):
        return self.syscontainers.has_image(img)

    def has_container(self, container):
        return self.syscontainers.get_checkout(container) is not None

    def inspect_image(self, image):
        return self._make_image(self.syscontainers.inspect_system_image(image))

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
        return self.syscontainers.get_system_images(get_all=get_all)

    def get_containers(self):
        return [self._make_container(x) for x in self.syscontainers.get_containers()]

    def pull_image(self, image):
        return self.syscontainers.pull_image(image)

    def delete_image(self, image, force=False):
        return self.syscontainers.delete_image(image)

    def version(self, image):
        return self.syscontainers.version(image)

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

