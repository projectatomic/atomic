from Atomic.util import output_json
from Atomic.client import no_shaw

class Layer(object): # pylint: disable=eq-without-hash
    def __init__(self, img_input):
        self.id = None
        self.name = None
        self.version = None
        self.release = None
        self.repotags = None
        self.parent = None
        self.remote = False
        self.digest = None
        self.backend = None

        if type(img_input) is dict:
            pass
        else:
            self._instantiate_from_image_object(img_input)

    def _instantiate_from_image_object(self, img_obj):
        self.id = img_obj.id
        self.name = img_obj.get_label('Name') or img_obj.name or img_obj.image
        self.remote = img_obj.remote
        self.version = img_obj.version
        self.release = img_obj.release
        self.repotags = img_obj.repotags
        # This needs to be resolved for future docker versions
        self.parent = img_obj.parent
        self.digest = img_obj.digest
        self.backend = img_obj.backend
        return self

    def _instantiate_from_dict(self):
        return self

    def __eq__(self, other):
        if self.long_version == other.long_version:
            return True
        return False

    def __ne__(self, other):
        if self.long_version != other.long_version:
            return True
        return False

    def dump(self):
        # helper function to dump out known variables/values in pretty-print style
        class_vars = dict(vars(self))
        foo = {x: class_vars[x] for x in class_vars if not callable(getattr(self, x)) and not x.startswith('__')
               and not x.endswith('_backend')}
        output_json(foo)

    @property
    def long_version(self):
        _version = ""
        if self.version:
            _version += "{}".format(self.version)
        if self.release:
            if self.version:
                _version += "-"
            _version += "{}".format(self.release)
        if not _version:
            return no_shaw(self.id or self.digest)
        return _version
