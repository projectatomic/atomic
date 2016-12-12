from Atomic.util import output_json
import datetime

class Container(object):
    def __init__(self, input_name, backend=None):

        # Required
        self.name = None
        self.id = None
        self._created = None
        self.status = None
        self.input_name = input_name
        self.original_structure = None
        self.deep = False
        self._backend = backend
        self.runtime = backend.backend
        self.image_id = None
        self.image_name = None
        self.command = None
        self.state = None
        self.vulnerable = False
        self.labels = None

        # Optional
        self.running = False
        # Instantiate
        self._instantiate()
        self.stop_args = None

    def _instantiate(self):
        self._setup_common()
        return self

    def _setup_common(self):
        # Items common to backends can go here.
        pass

    def get_label(self, label):
        if self.labels:
            return self.labels.get(label.lower(), None) or self.labels.get(label.upper(), None)
        return None

    def dump(self):
        # Helper function to dump out known variables in pretty-print style
        class_vars = dict(vars(self))
        foo = {x: class_vars[x] for x in class_vars if not callable(getattr(self, x)) and not x.startswith('__')
               and not x.endswith('_backend')}
        output_json(foo)

    @property
    def backend(self):
        return self._backend

    @backend.setter
    def backend(self, value):
        self._backend = value

    @property
    def created(self):
        return str(datetime.datetime.fromtimestamp(self._created))

    @property
    def created_raw(self):
        return self._created

    @created.setter
    def created(self, value):
        self._created = value
