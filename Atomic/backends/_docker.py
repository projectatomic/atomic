from docker import errors

import Atomic.util as util
from Atomic.backends.backend import Backend
from Atomic.client import get_docker_client
from Atomic.objects.image import Image
from Atomic.objects.container import Container
from requests import exceptions


class DockerBackend(Backend):
    def __init__(self):
        self.input = None
        self.img_obj = None
        self.d = get_docker_client()
        self._ping()

    @property
    def backend_type(self):
        return "docker"

    def has_image(self, img):
        '''
        Checks is the img is a image ID or a matches an image name.
        If it finds a match, it returns the full image ID. Else it will
        return an AtomicError.
        '''
        err_append = "Refine your search to narrow results."
        self.input = img
        image_info = self.get_docker_images()

        inspect = self._inspect_image(image=img)
        if inspect is not None:
            self.inspect = inspect
            return True

        name_search = util.image_by_name(img, images=image_info)
        if len(name_search) > 0:
            if len(name_search) > 1:
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
            return True
        # No dice
        return False

    def has_container(self, container):
        if self._inspect_container(container) is not None:
            self.input = container
            return True
        return False

    def _inspect_image(self, image):
        try:
            inspect_data = self.d.inspect_image(image)
        except errors.NotFound:
            return None
        return inspect_data

    def inspect_image(self, image):
        if not self.img_obj or getattr(self.img_obj, "input_name", None) != image:
            inspect_data = self._inspect_image(image)
            self.img_obj = self._make_image(image, inspect_data, deep=True)
        return self.img_obj

    @staticmethod
    def _get_label_from_config(config, label):
        if config.get('Labels'):
            return config['Labels'].get(label, None)

    def _make_image(self, image, img_struct, deep=False):
        img_obj = Image(image)
        img_obj.id = img_struct['Id']
        img_obj._backend = self
        img_obj.repotags = img_struct['RepoTags']
        img_obj.created = img_struct['Created']
        img_obj.size = img_struct['Size']

        if deep:
            img_obj.deep = True
            img_obj.repotags = img_struct['RepoTags']
            img_obj.config = img_struct['Config'] or {}
            img_obj.labels = img_obj.config.get("Labels", None)
            img_obj.os = img_struct['Os']
            img_obj.arch = img_struct['Architecture']
            img_obj.graph_driver = img_struct['GraphDriver']
            img_obj.version = self._get_label_from_config(img_obj.config, 'Version')
            img_obj.release = self._get_label_from_config(img_obj.config, 'Release')
        return img_obj

    def _make_container(self, container, con_struct, deep=False):
        con_obj = Container(container)
        con_obj.id = con_struct['Id']
        con_obj.created = con_struct['Created']
        con_obj.original_structure = con_struct
        con_obj.input_name = container
        con_obj.__backend = self

        if not deep:
            con_obj.status = con_struct['Status']
            con_obj.image = con_struct['ImageID']

        if deep:
            # Add in the deep inspection stuff
            con_obj.status = con_struct['State']['Status']
            con_obj.running = con_struct['State']['Running']

        return con_obj

    def _inspect_container(self, container):
        try:
            inspect_data = self.d.inspect_container(container)
        except errors.NotFound:
            return None
        return inspect_data

    def inspect_container(self, container):
        inspect_data = self._inspect_container(container)
        return self._make_container(container, inspect_data, deep=True)

    def get_images(self):
        images = self.get_docker_images()
        image_objects = []
        for image in images:
            image_objects.append(self._make_image(image['Id'], image))
        return image_objects

    def get_containers(self):
        containers = self.get_docker_containers()
        con_objects = []
        for con in containers:
            #print(con)
            con_objects.append(self._make_container(con['Id'], con))
        return con_objects

    def get_docker_images(self):
        return self.d.images(all=True)

    def get_docker_containers(self):
        return self.d.containers(all=True)

    def start_container(self, name):
        if not self.has_container(name):
            raise ValueError("Unable to locate container '{}' in {} backend".format(name, self.backend_type))
        return self.d.start(name)

    def stop_container(self, name):
        stop_obj = self.inspect_container(name)
        if not stop_obj:
            raise ValueError("Unable to find container '{}'".format(name))
        if not stop_obj.running:
            raise ValueError("Container '{}' is not running".format(name))
        return self.d.stop(name)

    def pull_image(self, image):
        # Should be replaced with Atomic.pull.pull_docker_image
        pass

    def delete_container(self, id, force=False):
        self.d.remove_container(id, force=force)

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

