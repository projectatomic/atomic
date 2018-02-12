from Atomic.backends._docker import DockerBackend
from Atomic.backends._docker_errors import NoDockerDaemon
from Atomic.backends._ostree import OSTreeBackend
from Atomic.backends._containers_storage import ContainersStorageBackend
from Atomic.util import write_out, get_atomic_config

ATOMIC_CONFIG = get_atomic_config()
default_storage = ATOMIC_CONFIG.get('default_storage', "docker")

class BackendUtils(object):
    """
    Given an image, returns the back end that owns that image
    """

    BACKENDS = [DockerBackend, OSTreeBackend, ContainersStorageBackend]

    @property
    def available_backends(self):
        return self._set_available_backends()

    def _set_available_backends(self):
        bes = []
        for x in self.BACKENDS:
            try:
                be = x()
                if be.available:
                    bes.append(x)
            except NoDockerDaemon:
                pass
        if len(bes) < 1:
            raise ValueError("No backends are enabled for Atomic.")
        return bes

    def dump_backends(self):
        backends = ''
        for i in self.available_backends:
            be = i()
            backends += "{}: Active, ".format(be.backend)
        write_out("Backends({})\n".format(backends))

    def get_backend_from_string(self, str_backend, init=True):
        for _backend in self.BACKENDS:
            backend = _backend
            backend_obj = _backend()
            if backend_obj.backend == str_backend:
                if init:
                    return backend_obj
                return backend
        raise ValueError("Unable to associate string '{}' with backend".format(str_backend))

    def _get_backend(self, backend):
        return self.get_backend_from_string(backend, init=False)

    @staticmethod
    def backend_has_image(backend, img):
        return True if backend.has_image(img) else False

    @staticmethod
    def backend_has_container(backend, container):
        return True if backend.has_container(container) else False

    def get_backend_and_image_obj(self, img, str_preferred_backend=None, required=False):
        """
        Given an image name (str) and optionally a str reference to a backend,
        this method looks for the image firstly on the preferred backend and
        then on the alternate backends.  It returns a backend object and an
        image object.
        :param img: name of image to look for
        :param str_preferred_backend: i.e. 'docker'
        :return: backend object and image object
        """
        backends = list(self.available_backends)

        if str_preferred_backend and self._get_backend(str_preferred_backend) not in self.available_backends and required:
            raise ValueError("The '{}' backend appears unavailable/inactive".format(str_preferred_backend))
        # Check preferred backend first
        if str_preferred_backend and self._get_backend(str_preferred_backend) in self.available_backends:
            be = self.get_backend_from_string(str_preferred_backend)
            img_obj = be.has_image(img)
            if img_obj:
                return be, img_obj
            if required:
                raise ValueError("Unable to find {} in the {} backend".format(img, str_preferred_backend))
            # Didnt find in preferred, need to remove it from the list now
            if be in backends:
                del backends[backends.index(be)]

        # Did not find it in the preferred backend, keep looking
        img_in_backends = []
        for backend in backends:
            be = backend()
            img_obj = be.has_image(img)
            if img_obj:
                img_in_backends.append((be, img_obj))

        if len(img_in_backends) == 1:
            return img_in_backends[0]
        if len(img_in_backends) == 0:
            raise ValueError("Unable to find '{}' in the following backends: {}".format(img, ", ".join([x().backend for x in self.available_backends])))
        raise ValueError("Found {} in multiple storage backends: {}".
                         format(img, ', '.join([x.backend for x, _ in img_in_backends])))

    def get_backend_and_container_obj(self, container_name, str_preferred_backend=None, required=False):
        """
        Given a container name (str) and optionally a str reference to a backend,
        this method looks for the container firstly on the preferred backend and
        then on the alternate backends.  It returns a backend object and a container
        object.
        :param container_name: name of image to look for
        :param str_preferred_backend: i.e. 'docker'
        :return: backend object and container object
        """

        if str_preferred_backend and self._get_backend(str_preferred_backend) not in self.available_backends and required:
            raise ValueError("The '{}' backend appears unavailable/inactive".format(str_preferred_backend))

        backends = list(self.available_backends)
        # Check preferred backend first
        if str_preferred_backend and self._get_backend(str_preferred_backend) in self.available_backends:
            be = self.get_backend_from_string(str_preferred_backend)
            con_obj = be.has_container(container_name)
            if con_obj:
                return be, con_obj
            if required:
                raise ValueError("Unable to find {} in the {} backend".format(container_name, str_preferred_backend))
            # Didnt find in preferred, need to remove it from the list now
            if be in backends:
                del backends[backends.index(be)]

        container_in_backends = []
        for backend in backends:
            be = backend()
            con_obj = be.has_container(container_name)
            if con_obj:
                container_in_backends.append((be, con_obj))
        if len(container_in_backends) == 1:
            return container_in_backends[0]
        if len(container_in_backends) == 0:
            raise ValueError("Unable to find backend associated with container '{}'".format(container_name))
        raise ValueError("Found {} in multiple storage backends: {}".
                         format(container_name, ', '.join([x.backend for x in container_in_backends])))

    def get_images(self, get_all=False):
        backends = self.available_backends
        img_objs = []
        for backend in backends:
            be = backend()
            img_objs += be.get_images(get_all=get_all)
        return img_objs

    def get_containers(self):
        backends = self.available_backends
        con_objs = []
        for backend in backends:
            be = backend()
            con_objs += be.get_containers()
        return con_objs

    def get_container_obj_by_image_name(self, image_name, str_preferred_backend):
        pass

    @staticmethod
    def message_backend_change(previous, new):
        write_out("\nNote: Switching from the '{}' backend to the '{}' backend based on the 'atomic.type' label in the "
                  "image.  You can use --storage to override this behaviour.\n".format(previous, new))

