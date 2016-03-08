#!/usr/bin/env python

# Author: Dan Walsh <dwalsh@redhat.com>
from distutils.core import setup
import Atomic as _Atomic

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name="atomic", scripts=["atomic", "atomic_dbus.py"],
    version=_Atomic.__version__,
    author=_Atomic.__author__,
    author_email=_Atomic.__author_email__,
    packages=["Atomic"],
    data_files=[('/etc/dbus-1/system.d/', ["org.atomic.conf"]),
                ('/usr/share/dbus-1/system-services', ["org.atomic.service"]),
                ('/usr/share/polkit-1/actions/', ["org.atomic.policy"]),
                ("/usr/share/bash-completion/completions/",
                 ["bash/atomic"])]
)
