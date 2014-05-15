"""
Creates the operating system package.
"""
from rez.package_maker_ import make_py_package
from rez.exceptions import RezBindError
from rez.vendor.version.version import Version
from rez.system import system


def bind(path, version_range=None, opts=None, parser=None):
    version = Version(system.os)
    if version_range and version not in version_range:
        raise RezBindError("detected operating system %s does not match %s"
                           % (str(version), str(version_range)))

    with make_py_package("os", version, path) as pkg:
        pkg.set_requires("platform-%s" % system.platform,
                         "arch-%s" % system.arch)

    return ("os", version)
