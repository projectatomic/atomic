#!/usr/bin/env python

# Author: Dan Walsh <dwalsh@redhat.com>
import os
from distutils.core import setup

setup(name = "atomic", scripts=["atomic"], version="1.0", description="Atomic Management Tool", author="Daniel Walsh", author_email="dwalsh@redhat.com", packages=["atomicpulp"])
