from .pulp import PulpServer, PulpConfig
from .satellite import SatelliteServer, SatelliteConfig
from .atomic import Atomic
from .util import write_out

#https://bitbucket.org/logilab/pylint/issues/36/
#pylint: disable=no-member

# When changinig the version here, also change in the
# .copr/atomic.spec line 18.
__version__ = '1.22.1'
__author__  = 'Daniel Walsh'
__author_email__ = 'dwalsh@redhat.com'

