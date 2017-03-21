from Atomic.util import output_json
import datetime

class Container(object):
    def __init__(self, input_name, backend=None):

        # Required
        self._name = None
        self.id = None
        self._created = None
        self.status = None
        self.input_name = input_name
        self.original_structure = None
        self.deep = False
        self._backend = backend
        self.runtime = backend.backend
        self.image = None
        self.image_name = None
        self._command = None
        self.state = None
        self.vulnerable = False
        self.labels = None
        self._user_command = None
        self.mount_path = None

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
    def type(self):
        return 'container'

    @property
    def created(self):
        return str(datetime.datetime.fromtimestamp(self._created))

    @property
    def created_raw(self):
        return self._created

    @created.setter
    def created(self, value):
        self._created = value

    @property
    def command(self):
        cmd = self._command if self._command is not None else ['/bin/sh']
        return  cmd

    @command.setter
    def command(self, value):
        self._command = value

    @property
    def interactive(self):
        config = self.original_structure['Config']
        if all([config.get('AttachStdin', False), config.get('AttachStdout', False), config.get('AttachStderr', False)]):
            return True
        return False

    @property
    def name(self):
        return str(self._name)

    @name.setter
    def name(self, value):
        self._name = value[1:] if value[0] == '/' else value

    @property
    def user_command(self):
        return self._user_command

    @user_command.setter
    def user_command(self, value):
        self._user_command = value

