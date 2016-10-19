from Atomic.util import output_json


class Container(object):
    def __init__(self, input_name):

        # Required
        self.name = None
        self.id = None
        self.created = None
        self.status = None
        self.input_name = input_name
        self.original_structure = None
        self.deep = False
        self.__backend = None
        self.image = None

        # Optional
        self.running = False
        # Instantiate
        self._instantiate()

    def _instantiate(self):
        self._setup_common()
        return self

    def _setup_common(self):
        # Items common to backends can go here.
        print("")

    def dump(self):
        # Helper function to dump out known variables in pretty-print style
        class_vars = dict(vars(self))
        foo = {x: class_vars[x] for x in class_vars if not callable(getattr(self, x)) and not x.startswith('__')}
        output_json(foo)