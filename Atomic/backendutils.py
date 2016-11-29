from Atomic.backends._docker import DockerBackend
from Atomic.backends._ostree import OSTreeBackend


class BackendUtils(object):
    """
    Given an image, returns the back end that owns that image
    """

    BACKENDS = [DockerBackend, OSTreeBackend]

    def get_backend_from_string(self, str_backend):
        for _backend in self.BACKENDS:
            backend_obj = _backend()
            if backend_obj.backend == str_backend:
                return backend_obj
        raise ValueError("Unable to associate string '{}' with backend".format(str_backend))

    def _get_backend_index_from_string(self, str_backend):
        return [x().backend for x in self.BACKENDS].index(str_backend)

    @staticmethod
    def backend_has_image(backend, img):
        return True if backend.has_image(img) else False

    @staticmethod
    def backend_has_container(backend, container):
        return True if backend.has_container(container) else False

    def get_backend_and_image(self, img, str_preferred_backend=None):
        """
        Given an image name (str) and optionally a str reference to a backend,
        this method looks for the image firstly on the preferred backend and
        then on the alternate backends.  It returns a backend object.
        :param img: name of image to look for
        :param str_preferred_backend: i.e. 'docker'
        :return: backend object
        """
        backends = list(self.BACKENDS)
        # Check preferred backend first
        if str_preferred_backend:
            be = self.get_backend_from_string(str_preferred_backend)
            img_obj = be.has_image(img)
            if img_obj:
                return be, img_obj

            # Didnt find in preferred, need to remove it from the list now
            del backends[self._get_backend_index_from_string(str_preferred_backend)]

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
            raise ValueError("Unable to find backend associated with image '{}'".format(img))
        raise ValueError("Found {} in multiple storage backends: {}".
                         format(img, ', '.join([x.backend for x in img_in_backends])))

    def get_backend_for_container(self, container, str_preferred_backend=None):
        """
        Given a container name (str) and optionally a str reference to a backend,
        this method looks for the container firstly on the preferred backend and
        then on the alternate backends.  It returns a backend object.
        :param container: name of image to look for
        :param str_preferred_backend: i.e. 'docker'
        :return: backend object
        """
        backends = list(self.BACKENDS)
        # Check preferred backend first
        if str_preferred_backend:
            be = self.get_backend_from_string(str_preferred_backend)
            if be.has_container(container):
                return be
            # Didnt find in preferred, need to remove it from the list now
            del backends[self._get_backend_index_from_string(str_preferred_backend)]

        container_in_backends = []
        for backend in backends:
            be = backend()
            if be.has_container(container):
                container_in_backends.append(be)
        if len(container_in_backends) == 1:
            return container_in_backends[0]
        if len(container_in_backends) == 0:
            raise ValueError("Unable to find backend associated with container '{}'".format(container))
        raise ValueError("Found {} in multiple storage backends: {}".
                         format(container, ', '.join([x.backend for x in container_in_backends])))

    def get_images(self, get_all=False):
        backends = self.BACKENDS
        img_objs = []
        for backend in backends:
            be = backend()
            img_objs += be.get_images(get_all=get_all)
        return img_objs

    def get_containers(self):
        backends = self.BACKENDS
        con_objs = []
        for backend in backends:
            be = backend()
            con_objs += be.get_containers()
        return con_objs

