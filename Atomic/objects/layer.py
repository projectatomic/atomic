from Atomic.util import output_json

class Layer(object):
    def __init__(self, img_input):
        self.id = None
        self.name = None
        self.version = None
        self.repotags = None
        self.parent = None
        self.remote = False

        if type(img_input) is dict:
            pass
        else:
            self._instantiate_from_image_object(img_input)

    def _instantiate_from_image_object(self, img_obj):
        self.id = img_obj.id
        self.name = img_obj.name
        self.version = img_obj.version
        self.repotags = img_obj.repotags
        # This needs to be resolved for future docker versions
        self.parent = None
        return self

    def _instantiate_from_dict(self):
        return self

    def __gt__(self, other):
        pass


    def dump(self):
        # helper function to dump out known variables/values in pretty-print style
        class_vars = dict(vars(self))
        foo = {x: class_vars[x] for x in class_vars if not callable(getattr(self, x)) and not x.startswith('__')
               and not x.endswith('_backend')}
        output_json(foo)