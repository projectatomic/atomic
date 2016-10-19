from abc import abstractmethod, ABCMeta, abstractproperty


class Backend(object):
    # Mark the class as abstract
    __metaclass__ = ABCMeta

    @abstractproperty
    def backend(self):
        return 'Should never use this'

    @abstractmethod
    def inspect_image(self, image):
        # docker
        pass


    @abstractmethod
    def inspect_container(self, image):
        # docker
        pass

    @abstractmethod
    def pull_image(self):
        # docker - needs last minute move
        pass

    @abstractmethod
    def install(self, image, name):
        pass

    @abstractmethod
    def uninstall(self, name):
        pass

    @abstractmethod
    def version(self, image):
        pass

    @abstractmethod
    def update(self, name, force=False):
        # docker
        pass

    @abstractmethod
    def get_containers(self):
        # docker
        pass

    @abstractmethod
    def get_images(self, get_all=False):
        # docker
        pass

    @abstractmethod
    def delete_image(self, image, force=False):
        # docker
        pass

    @abstractmethod
    def start_container(self, name):
        # docker
        pass

    @abstractmethod
    def stop_container(self, name):
        # docker
        pass

    @abstractmethod
    def prune(self):
        pass

    @abstractmethod
    def has_image(self, img):
        # docker
        pass

    @abstractmethod
    def has_container(self, container):
        # docker
        pass

    @abstractmethod
    def validate_layer(self, layer):
        pass

