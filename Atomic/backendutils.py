from Atomic.backends._docker import DockerBackend
from Atomic.backends._syscontainers import SysContainersBackend


class BackendUtils():
    """
    Given an image, returns the back end that owns that image
    """

    BACKENDS = [DockerBackend, SysContainersBackend]

    def get_backend_for_image(self, img):
        for backend in self.BACKENDS:
            be = backend()
            if be.has_image(img):
                return be
        raise ValueError("Unable to find backend associated with image'{}'".format(img))

    def get_backend_for_container(self, container):
        for backend in self.BACKENDS:
            be = backend()
            if be.has_container(container):
                return be
        raise ValueError("Unable to find backend associated with container '{}'".format(container))



