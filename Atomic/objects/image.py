from Atomic.util import Decompose, output_json
from Atomic.discovery import RegistryInspect


class Image(object):
    def __init__(self, input_name):

        # Required
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
        self._backend = None
        self.input_name = input_name
        self.deep = False

        # Deeper
        self.version = None
        self.release = None
        self.digest = None
        self.labels = None
        self.os = None
        self.arch = None
        self.graph_driver = None
        self.config = None
        self._fq_name = None

        self._instantiate()

    def __gt__(self, other):
        """
        Custom greater than comparison between image objects. This allows you to
        determine if an image object is "newer" than another.

        Looking into other ways to possibly approach this.
        """
        pass

    def _instantiate(self):
        self._setup_common()
        return self

    def _setup_common(self):
        # Items common to backends can go here.
        self.registry, self.repo, self.image, self.tag, self.digest = Decompose(self.input_name).all

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
        if self._fq_name:
            return self._fq_name
        registry, repo, image, tag, _ = Decompose(self.input_name).all
        if not image:
            raise ValueError('Error parsing input: "{}" invalid'.format(self.input_name))
        if all([True if x else False for x in [registry, image, tag]]):
            img = registry
            if repo:
                img += "/{}".format(repo)
            img += "/{}:{}".format(image, tag)
            return img
        if not registry:
            ri = RegistryInspect(registry, repo, image, tag, orig_input=self.input_name)
            self._fq_name = ri.find_image_on_registry()
            return self._fq_name

    @property
    def backend(self):
        return self._backend



