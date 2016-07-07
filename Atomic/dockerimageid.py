import json
import docker
from Atomic.client import get_docker_client
from Atomic.util import check_if_python2


class DockerImageID(object):
    """
    Custom Object class for dealing with the pre-pended
    sha algorithm now present in Docker Image IDS.
    """
    ALGO = "sha256:"

    def __init__(self, input_id):
        self.id = input_id

    def __str__(self):
        """
        Returns string representation of a object without
        the sha algorithm
        """
        return self.id.replace(self.ALGO, "")

    def __eq__(self, other):
        """
        Performs an equality check between two docker objects
        or their string representations.
        """
        if self.id == other or self.id.startswith(str(other)):
            return True
        elif str(self) == other or str(self).startswith(str(other)):
            return True
        return False

    def __ne__(self, other):
        """
        Performs an in-equality check between two docker objects
        or their string representations.
        """
        if not self.__eq__(other):
            return True
        else:
            return False

    def __repr__(self):
        """
        Returns string representation of a object without
        the sha algorithm
        """
        return "'%s'" % self.id.replace(self.ALGO, "")

    @staticmethod
    def dockerid_to_json(obj):
        """
        A generic function that can be used for things
        like JSON serialization.  Currently returns a
        string which not include the sha algo.
        """
        return str(obj)

    @staticmethod
    def print_json(json_data):
        print(json.dumps(json_data, indent=4, separators=(',', ': '), default=DockerImageID.dockerid_to_json))

is_python2 = check_if_python2()[1]

# Known keys that contain sha26: preceding value
SUB_KEYS = ['Parent', 'Id', 'Image']

def iter_subs(tree, key=None):
    """
    Takes a structure like a dict, list of dicts ... and
    recursively walks the structure to replace any value it
    finds that starts with the algo with a DockerID object.
    """
    if isinstance(tree, set):
        tree = set([iter_subs(x) for x in tree])
    elif isinstance(tree, frozenset):
        tree = frozenset([iter_subs(x) for x in tree])
    elif isinstance(tree, str):
        if str(tree).startswith(DockerImageID.ALGO) and key in SUB_KEYS:
            return DockerImageID(str(tree))
    # In py2, it is unicode and not str
    elif is_python2 and isinstance(tree, unicode) and key in SUB_KEYS: # pylint: disable=undefined-variable
        if str(tree).startswith(DockerImageID.ALGO):
            return DockerImageID(str(tree))
    elif isinstance(tree, dict):
        for k, v in tree.items():
            tree[k] = iter_subs(v, key=k)
    elif isinstance(tree, list):
        for i in range(len(tree)):
            tree[i] = iter_subs(tree[i])
    return tree
