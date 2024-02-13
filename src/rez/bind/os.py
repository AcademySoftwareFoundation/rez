# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the Rez Project


"""
Creates the operating system package.
"""
from rez.package_maker import make_package
from rez.version import Version
from rez.bind._utils import check_version
from rez.system import system


def bind(path, version_range=None, opts=None, parser=None):
    version = Version(system.os)
    check_version(version, version_range)

    with make_package("os", path) as pkg:
        pkg.version = version
        pkg.requires = [
            "platform-%s" % system.platform,
            "arch-%s" % system.arch
        ]

    return pkg.installed_variants
