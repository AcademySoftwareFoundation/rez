"""
Creates the operating system package.
"""
from __future__ import absolute_import
from rez.package_maker__ import make_package
from rez.vendor.version.version import Version
from rez.bind._utils import check_version
from rez.system import system


def bind(path, version_range=None, opts=None, parser=None):
    version = Version(system.os)
    check_version(version, version_range)

    with make_package("os", path) as pkg:
        pkg.version = version
        pkg.requires = ["platform-%s" % system.platform,
                         "arch-%s" % system.arch]

    return "os", version
