# pylint: disable=unused-import
# pylint: disable=unused-argument

import Atomic.util as util
from abc import abstractmethod, ABCMeta, abstractproperty
from Atomic.objects.image import Image
from Atomic.objects.container import Container
from Atomic.trust import Trust
import os
import json
import datetime as DT
import time
from Atomic.backends.backend import Backend
try:
    from subprocess import DEVNULL  # pylint: disable=no-name-in-module
except ImportError:
    DEVNULL = open(os.devnull, 'wb')


class UnderDevelopment(Exception):
    def __init__(self):
        super(UnderDevelopment, self).__init__("This function for containers-storage is still under development.")


class ContainersStorageBackend(Backend): #pylint: disable=metaclass-assignment
    # Mark the class as abstract
    __metaclass__ = ABCMeta

    @property
    def backend(self):
        return 'containers-storage'

    def _inspect_image(self, image):
        return json.loads(util.kpod(['inspect', image]))

    def inspect_image(self, image):
        """
        Returns the results of an inspected image as an image object
        :param image:
        :return: img_obj
        """
        inspect_data = self._inspect_image(image)
        if not inspect_data:
            return None
        return self._make_image(image, inspect_data, deep=True)

    def _inspect_container(self, container):
        return json.loads(util.kpod(['inspect', container]))

    def inspect_container(self, container):
        """
        Inspect a container
        :param container:
        :return: con_obj
        """
        inspect_data = self._inspect_container(container)
        if inspect_data:
            return self._make_container(container, inspect_data, deep=True)
        return None

    def pull_image(self, image, remote_image_obj, **kwargs):
        """
        Pulls an image to the backend
        :param image:
        :param pull_args:
        :return:
        """
        debug = kwargs.get('debug', False)
        fq_name = remote_image_obj.fq_name
        registry, _, _, tag, _ = util.Decompose(fq_name).all
        if not image.endswith(tag):
            image += ":{}".format(tag)
        if '@sha256:' in image:
            image = image.replace("@sha256:", ":")

        insecure = False
        registries_config = util.load_registries_from_yaml()
        if "insecure_registries" in registries_config:
            if registry in registries_config['insecure_registries']:
                insecure = True
        source = "docker://{}".format(image)
        dest = "containers-storage:{}".format(image)
        trust = Trust()
        trust.discover_sigstore(fq_name)
        util.write_out("Pulling {} ...".format(fq_name))
        util.skopeo_copy(source, dest, debug=debug, insecure=insecure, policy_filename=trust.policy_filename)
        return 0

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

    # This needs to be fixed if the notion of dangling becomes real
    # for containers-image.

    def _make_container(self, container, con_struct, deep=False):
        con_obj = Container(container, backend=self)
        if not deep:
            con_obj.id = con_struct['id']
            con_obj.image = con_struct['image_id']
            con_obj.image_name = con_struct['image']
            con_obj.created = time.mktime(time.strptime(con_struct['createdAt'].split(".")[0], "%Y-%m-%dT%H:%M:%S"))
            con_obj.status = con_struct['status']
            con_obj.state = con_obj.status.split()[0]
            con_obj.name = con_struct['names']
            con_obj.labels = con_struct['labels']
            con_obj.running = True if con_obj.status.lower().startswith("up") else False
            con_obj.runtime = "runc"
        else:
            con_obj.id = con_struct['ID']
            con_obj.image = con_struct['ImageID']
            con_obj.image_name = con_struct['Image']
            con_obj.created = time.mktime(time.strptime(con_struct['State']['created'].split(".")[0], "%Y-%m-%dT%H:%M:%S"))
            con_obj.command = con_struct['Config']['Cmd']
            con_obj.state = con_struct['State']['status']
            con_obj.running = True if con_obj.state.upper() not in ['STOPPED'] else False
            con_obj.name = con_struct['Name']
            con_obj.labels = con_struct['Labels']
            con_obj.original_structure = con_struct

        return con_obj

    def get_containers(self):
        """
        Get containers for the backend
        :return: list of container objects
        """
        containers = json.loads(util.kpod(["ps", "-a", "--format", "json"]))
        container_objects = []
        for container in containers:
            container_objects.append(self._make_container(container['id'], container))
        return container_objects

    def _make_image(self, image, img_struct, deep=False, remote=False):
        img_obj = Image(image, remote=remote)
        img_obj.backend = self
        if not remote and not deep:
            img_obj.size = img_struct['size']
            img_obj.virtual_size = img_obj.size
            img_obj.version = img_obj.version
            img_obj.repotags = img_struct['names']

        if not remote:
            try:
                img_obj.id = img_struct['id']
            except KeyError:
                img_obj.id = img_struct['ID']
            try:
                img_obj.created = DT.datetime.strptime(img_struct['created'], "%b %d, %Y %H:%M").strftime("%Y-%m-%d %H:%M")
            except KeyError:
                img_obj.created = time.mktime(time.strptime(img_struct['Created'].split(".")[0], "%Y-%m-%dT%H:%M:%S"))
            try:
                img_obj.size = img_struct['size']
            except KeyError:
                img_obj.size = img_struct['Size']
            try:
                img_obj.digest = img_struct['digest']
            except KeyError:
                img_obj.digest = img_struct['Digest']

        if deep:
            img_obj.deep = True
            img_obj.repotags = img_struct['Tags']
            img_obj.config = img_struct['Config'] or {}
            img_obj.labels = img_obj.config.get("Labels", None)
            img_obj.os = img_struct['OS']
            img_obj.arch = img_struct['Architecture']
            img_obj.graph_driver = img_struct['GraphDriver']
            img_obj.version = img_obj.get_label('Version')
            img_obj.release = img_obj.get_label('Release')
            # kpod inspect has no Parent right now
            #img_obj.parent = img_struct['Parent']
            img_obj.original_structure = img_struct
            img_obj.cmd = img_obj.original_structure['Config']['Cmd']

        return img_obj

    def make_remote_image(self, image):
        img_obj = self._make_remote_image(image)
        img_obj.populate_remote_inspect_info()
        return img_obj

    def _make_remote_image(self, image):
        return self._make_image(image, None, remote=True)

    def get_images(self, get_all=False):
        """
        Get images for the backend
        :param get_all: bool
        :return:  list of image objects
        """
        images = json.loads(util.kpod(["images", "--format", "json"]))
        image_objects = []
        for image in images:
            image_objects.append(self._make_image(image['id'], image))
        return image_objects

    def get_dangling_images(self, force_update=True):
        images = json.loads(util.kpod(["images", "--filter", "dangling=true", "--format", "json"]))
        return [x['id'] for x in images]


    def delete_image(self, image, force=False):
        """
        Delete image
        :param image:
        :param force:
        :return:
        """
        assert(image is not None)
        cmd = ["rmi"]
        if force:
            cmd.append("-f")
        cmd.append(image)
        util.kpod(cmd)

    def delete_container(self, container, force=False):
        raise UnderDevelopment()

    def start_container(self, name):
        raise UnderDevelopment()

    def stop_container(self, con_obj, **kwargs):
        # If we plant to honor stop labels here, we will
        # need to implement that when kpod exec is available.
        return util.kpod(["stop", con_obj.id])


    def prune(self):
        for iid in self.get_dangling_images():
            self.delete_image(iid, force=True)
            util.write_out("Removed dangling Image {}".format(iid))

    def has_image(self, img):
        """
        Returns an img object if backend has the image or None
        :param img:
        :return:  img_obj or None
        """
        img_obj = self.inspect_image(img)
        if img_obj:
            return img_obj
        return None

    def has_container(self, container):
        """
        Returns a container obj if valid or None
        :param container:
        :return:
        """
        con_obj = self.inspect_container(container)
        if con_obj:
            return con_obj
        return None

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

    def tag_image(self, _src, _dest):
        cmd = ['tag', _src, _dest]
        return util.kpod(cmd)
