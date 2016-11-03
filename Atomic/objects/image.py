from Atomic.util import Decompose, output_json
from Atomic.discovery import RegistryInspect


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
            print(self.image)
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

    def remote_inspect(self):
        ri = RegistryInspect(registry=self.registry, repo=self.repo, image=self.image,
                             tag=self.tag, orig_input=self.input_name)
        ri.ping()
        remote_inspect_info = ri.inspect()
        self.created = remote_inspect_info['Created']
        self.name = remote_inspect_info['Name']
        self.os = remote_inspect_info['Os']
        self.digest = remote_inspect_info['Digest']
        self.arch = remote_inspect_info['Architecture']
        self.repotags = remote_inspect_info['RepoTags']
        self.labels = remote_inspect_info.get("Labels", None)
        self.release = self.get_label('Release')
        self.version = self.get_label('Version')

    @property
    def long_version(self):
        _version = ""
        label_name = self.get_label("Name")
        if label_name:
            _version += "{}".format(label_name)
        if self.version:
            _version += "-{}".format(self.version)
        if self.release:
            _version += "-{}".format(self.release)
        return _version