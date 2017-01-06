from Atomic.util import Decompose, output_json
from Atomic.discovery import RegistryInspect
from Atomic.objects.layer import Layer
import math
import time


class Image(object):
    def __init__(self, input_name, remote=False, backend=None):

        # Required
        self.remote = remote
        self.name = None
        self.id = None
        self.registry = None
        self.repo = None
        self.image = None
        self.tag = None
        self.repotags = None
        self.created = None
        self.size = None
        self.original_structure = None
        self._backend = backend
        self.input_name = input_name
        self.deep = False
        self._virtual_size = None

        # Deeper
        self.version = None
        self.release = None
        self.parent = None
        self.digest = None
        self.labels = None
        self.os = None
        self.arch = None
        self.graph_driver = None
        self.config = {}
        self._fq_name = None

        self._used = False
        self._vulnerable =  False

        self._template_variables_set = None
        self._template_variables_unset = None

        self._instantiate()


    def __gt__(self, other):
        """
        Custom greater than comparison between image objects. This allows you to
        determine if an image object is "newer" than another.

        Looking into other ways to possibly approach this.
        """
        pass

    def __eq__(self, other):
        if self.long_version == other.long_version:
            return True
        return False

    def __ne__(self, other):
        if self.long_version != other.long_version:
            return True
        return False

    def _instantiate(self):
        self._setup_common()
        return self

    def _setup_common(self):
        # Items common to backends can go here.
        decompose_name = self.input_name
        self.registry, self.repo, self.image, self.tag, self.digest = Decompose(decompose_name).all
        if not self.fully_qualified and self.remote:
            self.registry, self.repo, self.image, self.tag, self.digest = Decompose(self.fq_name).all
        if not self.image:
            raise ValueError('Cannot create image object: no image detected from "{}"'.format(decompose_name))

    def dump(self):
        # helper function to dump out known variables/values in pretty-print style
        class_vars = dict(vars(self))
        foo = {x: class_vars[x] for x in class_vars if not callable(getattr(self, x)) and not x.startswith('__')
               and not x.endswith('_backend')}
        output_json(foo)

    def _to_deep(self):
        return self.backend.inspect_image(self.id)

    @property
    def fq_name(self):
        def propagate(_img):
            if self.remote:
                self.registry, self.repo, self.image, self.tag, _ = Decompose(_img).all

        if self._fq_name:
            return self._fq_name

        if self.fully_qualified:
            img = self.registry
            if self.repo:
                img += "/{}".format(self.repo)
            img += "/{}:{}".format(self.image, self.tag)
            self._fq_name = img
            propagate(self._fq_name)
            return img

        if not self.registry:
            ri = RegistryInspect(registry=self.registry, repo=self.repo, image=self.image,
                                 tag=self.tag, orig_input=self.input_name)
            self._fq_name = ri.find_image_on_registry()
            propagate(self._fq_name)
            return self._fq_name

    @property
    def fully_qualified(self):
        return True if all([True if x else False for x in [self.registry, self.image, self.tag]]) else False

    @property
    def backend(self):
        return self._backend

    @backend.setter
    def backend(self, value):
        self._backend = value

    def get_label(self, label):
        if self.labels:
            if self.remote:
                return self.labels.get(label, None)
            return self.config['Labels'].get(label, None)
        return None

    def populate_remote_inspect_info(self):
        remote_inspect_info = self.remote_inspect()
        self.created = remote_inspect_info['Created']
        self.name = remote_inspect_info['Name']
        self.os = remote_inspect_info['Os']
        self.digest = remote_inspect_info['Digest']
        self.arch = remote_inspect_info['Architecture']
        self.repotags = remote_inspect_info['RepoTags']
        self.labels = remote_inspect_info.get("Labels", None)
        self.release = self.get_label('Release')
        self.version = self.get_label('Version')
        self.id = remote_inspect_info['id']

    def remote_inspect(self):
        ri = RegistryInspect(registry=self.registry, repo=self.repo, image=self.image,
                             tag=self.tag, orig_input=self.input_name)
        ri.ping()
        inspect_info = ri.inspect()
        #foo = ri.rc.manifest_json
        #inspect_info['id'] = ri.rc.manifest_json.get("config", None).get("digest", None)
        inspect_info['id'] = None if ri.rc.manifest_json.get("config", None) is None else ri.rc.manifest_json.get(
            "config", None).get("digest", None)
        return inspect_info

    @property
    def long_version(self):
        _version = ""
        if self.version:
            _version += "{}".format(self.version)
        if self.release:
            if self.version:
                _version += "-"
            _version += "{}".format(self.release)
        return _version

    @property
    def is_dangling(self):
        if self.id in self.backend.get_dangling_images():
            return True
        return False

    @property
    def virtual_size(self):
        size = self._virtual_size or self.size
        if size:
            return convert_size(self._virtual_size)
        return ""

    @virtual_size.setter
    def virtual_size(self, value):
        self._virtual_size = value

    @property
    def split_repotags(self):
        _repotags = []
        if not self.repotags:
            return [('<none>', '<none')]
        for _repotag in self.repotags:
            if ':' in _repotag:
                repo, tag = _repotag.rsplit(':', 1)
            else:
                repo = tag = ""
            _repotags.append((repo, tag))
        return _repotags

    @property
    def used(self):
        return self._used

    @used.setter
    def used(self, value):
        assert isinstance(value, bool)
        self._used = value

    @property
    def vulnerable(self):
        return self._vulnerable

    @vulnerable.setter
    def vulnerable(self, value):
        assert isinstance(value, bool)
        self._vulnerable = value

    @property
    def short_id(self):
        return self.id[:12]

    @property
    def timestamp(self):
        return time.strftime("%F %H:%M", time.localtime(self.created))

    @property
    def type(self):
        return self.backend.backend

    def _get_template_info(self):
        self._template_variables_set, self._template_variables_unset = self.backend.syscontainers.\
            get_template_variables(self.image)

    @property
    def template_variables_set(self):
        if self.backend.backend != 'ostree':
            return self._template_variables_set

        if not self._template_variables_set and not self.template_variables_unset:
            self._get_template_info()

        return self._template_variables_set

    @property
    def template_variables_unset(self):
        if self.backend.backend != ' ostree':
            return self._template_variables_unset

        if not self._template_variables_set and not self.template_variables_unset:
            self._get_template_info()
        return self._template_variables_unset

    @property
    def layers(self):
        layer_objects = []
        # Create the first layer
        layer = Layer(self)
        layer_objects.append(layer)
        while layer.parent:
            layer = self.backend.get_layer(layer.parent)
            layer_objects.append(layer)
        return layer_objects

def convert_size(size):
    if size > 0:
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = int(math.floor(math.log(size, 1000)))
        p = math.pow(1000, i)
        s = round(size/p, 2) # pylint: disable=round-builtin,old-division
        if s > 0:
            return '%s %s' % (s, size_name[i])
    return '0B'
