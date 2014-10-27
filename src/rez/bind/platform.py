"""
Creates the system platform package.
"""
from __future__ import absolute_import
from rez.package_maker_ import make_py_package
from rez.exceptions import RezBindError
from rez.vendor.version.version import Version
from rez.bind_utils import check_version
from rez.system import system


def bind(path, version_range=None, opts=None, parser=None):
    version = Version(system.platform)
    check_version(version, version_range)

    with make_py_package("platform", version, path) as pkg:
        pass

    return ("platform", version)
