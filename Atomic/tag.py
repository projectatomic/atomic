from . import Atomic
from . import util
from Atomic.backendutils import BackendUtils

ATOMIC_CONFIG = util.get_atomic_config()
storage = ATOMIC_CONFIG.get('default_storage', "docker")

class Tag(Atomic):
    def __init__(self):
        super(Tag, self).__init__()
        self.be = None

    def tag_image(self):
        """
        Tag an image with a different name
        :return: 0 if the tag was created
        """
        if self.args.debug:
            util.write_out(str(self.args))

        beu = BackendUtils()

        backend = None
        if self.args.storage:
            backend = beu.get_backend_from_string(self.args.storage)
            image  = backend.has_image(self.args.src)

        else:            
            backend, image = beu.get_backend_and_image_obj(self.args.src, required=False)

        if not backend or not image:
            raise ValueError("Cannot find image {}.".format(self.args.src))

        backend.tag_image(self.args.src, self.args.target)

        # We need to return something here for dbus
        return 0
