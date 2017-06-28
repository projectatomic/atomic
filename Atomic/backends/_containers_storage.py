# pylint: disable=unused-import
# pylint: disable=unused-argument

import Atomic.util as util
from abc import abstractmethod, ABCMeta, abstractproperty
from Atomic.objects.image import Image
from Atomic.objects.container import Container
import os

try:
    from subprocess import DEVNULL  # pylint: disable=no-name-in-module
except ImportError:
    DEVNULL = open(os.devnull, 'wb')


class UnderDevelopment(Exception):
    def __init__(self):
        super(UnderDevelopment, self).__init__("This function for containers_storage is still under development.")


class ContainersStorageBackend(object): #pylint: disable=metaclass-assignment
    # Mark the class as abstract
    __metaclass__ = ABCMeta

    @property
    def backend(self):
        return 'containers_storage'

    def inspect_image(self, image):
        """
        Returns the results of an inspected image as an image object
        :param image:
        :return: img_obj
        """
        raise UnderDevelopment()

    def inspect_container(self, container):
        """
        Inspect a container
        :param container:
        :return: con_obj
        """
        raise UnderDevelopment()

    def pull_image(self, image, remote_image_obj, **kwargs):
        """
        Pulls an image to the backend
        :param image:
        :param pull_args:
        :return:
        """
        raise UnderDevelopment()

    def install(self, image, name, **kwargs):
        """
        Installs an image on a backend
        :param image:
        :param name:
        :return:
        """
        raise UnderDevelopment()

    def uninstall(self, iobject, name=None, **kwargs):
        """
        Uninstalls an image from a backend
        :param name:
        :return:
        """
        raise UnderDevelopment()

    def version(self, image):
        """
        Return a list of layer objects
        :param image:
        :return:  list of layer objects
        """
        raise UnderDevelopment()

    def update(self, name, **kwargs):
        """
        Downloads latest image from registry
        :param image:
        :return:
        """
        raise UnderDevelopment()

    def get_containers(self):
        """
        Get containers for the backend
        :return: list of container objects
        """
        raise UnderDevelopment()

    def get_images(self, get_all=False):
        """
        Get images for the backend
        :param get_all: bool
        :return:  list of image objects
        """
        raise UnderDevelopment()

    def delete_image(self, image, force=False):
        """
        Delete image
        :param image:
        :param force:
        :return:
        """
        raise UnderDevelopment()

    def delete_container(self, container, force=False):
        raise UnderDevelopment()

    def start_container(self, name):
        raise UnderDevelopment()

    def stop_container(self, con_obj, **kwargs):
        raise UnderDevelopment()

    def prune(self):
        raise UnderDevelopment()

    def has_image(self, img):
        """
        Returns an img object if backend has the image or None
        :param img:
        :return:  img_obj or None
        """
        raise UnderDevelopment()

    def has_container(self, container):
        """
        Returns a container obj if valid or None
        :param container:
        :return:
        """
        raise UnderDevelopment()

    def validate_layer(self, layer):
        raise UnderDevelopment()

    def run(self, iobject, **kwargs):
        raise UnderDevelopment()

    @property
    def available(self):
        # When the ContainersStorageBackend is feature complete, the following
        # logic will need to be updated.
        if 'DEV' in os.environ:
            return True
        return False

    def tag_image(self, src, dest):
        raise UnderDevelopment()
