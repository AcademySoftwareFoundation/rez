"""
Creates the system architecture package.
"""
from rez.package_maker_ import make_py_package
from rez.exceptions import RezBindError
from rez.vendor.version.version import Version
from rez.system import system


def bind(path, version_range=None, opts=None, parser=None):
    version = Version(system.arch)
    if version_range and version not in version_range:
        raise RezBindError("detected architecture %s does not match %s"
                           % (str(version), str(version_range)))

    with make_py_package("arch", version, path) as pkg:
        pass

    return ("arch", version)
