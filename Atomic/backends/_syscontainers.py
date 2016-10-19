from Atomic.backends.backend import Backend
from Atomic.syscontainers import SystemContainers

class SysContainersBackend(Backend):
    @property
    def value(self):
        return "syscontainers"

    def has_image(self, img):
        sc = SystemContainers()
        return sc.has_image(img)
