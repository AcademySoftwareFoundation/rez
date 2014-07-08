"""
Utility for displaying help for the given package. This is determined via the 
'help' entry in the package.yaml, if that entry does not exist then an error 
results.
"""

from rez.config import config
from rez.packages import iter_package_families, iter_packages
from rez.vendor.version.version import VersionRange
from rez.vendor.version.requirement import Requirement
import os.path
import fnmatch
import sys


def setup_parser(parser):

    pass

def command(opts, parser):

    for package in iter_packages("ALF", range=None, timestamp=None, paths=None):
        if isinstance(package.help, basestring):
            help = package.help
        else:
            print package.help
            for v in package.iter_variants():
                print v.root
