import sys
import os
from pkg_resources import get_distribution
from .pulp import PulpServer, PulpConfig
from .satellite import SatelliteServer, SatelliteConfig
from .atomic import Atomic
from .util import writeOut

#https://bitbucket.org/logilab/pylint/issues/36/
#pylint: disable=no-member
__version__ = get_distribution('atomic').version
