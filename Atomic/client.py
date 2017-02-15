import docker
import sys
import requests
from Atomic.backends._docker_errors import NoDockerDaemon

def get_docker_client():
    """
    Universal method to use docker.client()
    """
    kwargs = {"version": "auto"}
    kwargs.update(docker.utils.kwargs_from_env(assert_hostname=False))
    try:
        client = docker.APIClient #pylint: disable=no-member
    except AttributeError:
        client = docker.Client #pylint: disable=no-member
    try:
        return client(**kwargs)
    except docker.errors.DockerException:
        raise NoDockerDaemon()

def check_if_python2():
    if int(sys.version_info[0]) < 3:
        _input = raw_input # pylint: disable=undefined-variable,raw_input-builtin
        return _input, True
    else:
        _input = input # pylint: disable=input-builtin
        return _input, False

class AtomicDocker():
    def __init__(self):
        self._client = None

    @property
    def _dockerclient(self):
        if not self._client:
            self._client = get_docker_client()
        return self._client

    def __dir__(self):
        return dir(self._dockerclient)

    def __repr__(self):
        return self._dockerclient.__repr__()

    def __enter__(self):
        return self

    def __exit__(self, typ, value, traceback):
        self.close()

    def __getattr__(self, name):
        return self.__getattribute__(name)

    def __getattribute__(self, name):
        # Avoid recursion for self._dockerclient
        if name == "_dockerclient" or name == "_client":
            return object.__getattribute__(self, name)
        obj = self._dockerclient
        try:
            attr = docker.Client.__getattribute__(obj, name) #pylint: disable=no-member
        except AttributeError:
            attr = docker.APIClient.__getattribute__(obj, name) #pylint: disable=no-member
        if hasattr(attr, '__call__'):
            def newfunc(*args, **kwargs):
                try:
                    result = attr(*args, **kwargs)
                    return iter_subs(result)
                except requests.exceptions.ConnectionError as e:
                    if name == "containers" or name == "images":
                        return []
                    raise e
            return newfunc
        else:
            return attr

    def close(self):
        if self._client != None:
            self._client.close()

is_python2 = check_if_python2()[1]

# Known keys that contain sha26: preceding value
SUB_KEYS = ['Parent', 'Id', 'Image', 'ImageID']
ALGO = "sha256:"


def no_shaw(value):
    return value.replace(ALGO, "")


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
        if str(tree).startswith(ALGO) and key in SUB_KEYS:
            return no_shaw(tree)
    # In py2, it is unicode and not str
    elif is_python2 and isinstance(tree, unicode) and key in SUB_KEYS: #pylint: disable=undefined-variable,unicode-builtin
        if str(tree).startswith(ALGO):
            return no_shaw(tree)
    elif isinstance(tree, dict):
        for k, v in tree.items():
            tree[k] = iter_subs(v, key=k)
    elif isinstance(tree, list):
        if is_python2:
            if all(isinstance(x, unicode) for x in tree) and all(j.startswith(ALGO) for j in tree): # pylint: disable=undefined-variable,unicode-builtin
                return [no_shaw(i) for i in tree]
        else:
            if all(isinstance(x, str) for x in tree) and all(j.startswith(ALGO) for j in tree):
                return [no_shaw(i) for i in tree]
        for i in range(len(tree)):
            tree[i] = iter_subs(tree[i])
    return tree
