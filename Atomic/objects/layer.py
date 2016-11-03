from Atomic.util import output_json

class Layer(object):
    def __init__(self, img_input):
        self.id = None
        self.name = None
        self.version = None
        self.release = None
        self.repotags = None
        self.parent = None
        self.remote = False

        if type(img_input) is dict:
            pass
        else:
            self._instantiate_from_image_object(img_input)

    def _instantiate_from_image_object(self, img_obj):
        self.id = img_obj.id
        self.name = img_obj.name or img_obj.get_label('Name') or img_obj.image
        self.version = img_obj.version
        self.release = img_obj.release
        self.repotags = img_obj.repotags
        # This needs to be resolved for future docker versions
        self.parent = img_obj.parent
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
        if self.name:
            _version += "{}".format(self.name)
        if self.version:
            _version += "-{}".format(self.version)
        if self.release:
            _version += "-{}".format(self.release)
        return _version
